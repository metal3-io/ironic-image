# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Cache for nodes currently under introspection."""

import collections
import contextlib
import copy
import datetime
import json
import operator

from automaton import exceptions as automaton_errors
from ironicclient import exceptions
from oslo_config import cfg
from oslo_db.sqlalchemy import utils as db_utils
from oslo_utils import excutils
from oslo_utils import reflection
from oslo_utils import timeutils
from oslo_utils import uuidutils
import six
from sqlalchemy.orm import exc as orm_errors

from ironic_inspector.common.i18n import _
from ironic_inspector.common import ironic as ir_utils
from ironic_inspector.common import locking
from ironic_inspector import db
from ironic_inspector import introspection_state as istate
from ironic_inspector import utils


CONF = cfg.CONF
LOG = utils.getProcessingLogger(__name__)
MACS_ATTRIBUTE = 'mac'


class NodeInfo(object):
    """Record about a node in the cache.

    This class optionally allows to acquire a lock on a node. Note that the
    class instance itself is NOT thread-safe, you need to create a new instance
    for every thread.
    """

    def __init__(self, uuid, version_id=None, state=None, started_at=None,
                 finished_at=None, error=None, node=None, ports=None,
                 ironic=None, manage_boot=True):
        self.uuid = uuid
        self.started_at = started_at
        self.finished_at = finished_at
        self.error = error
        self.invalidate_cache()
        self._version_id = version_id
        self._state = state
        self._node = node
        if ports is not None and not isinstance(ports, dict):
            ports = {p.address: p for p in ports}
        self._ports = ports
        self._attributes = None
        self._ironic = ironic
        # On upgrade existing records will have manage_boot=NULL, which is
        # equivalent to True actually.
        self._manage_boot = manage_boot if manage_boot is not None else True
        # This is a lock on a node UUID, not on a NodeInfo object
        self._lock = locking.get_lock(uuid)
        # Whether lock was acquired using this NodeInfo object
        self._fsm = None

    def __del__(self):
        if self._lock.is_locked():
            LOG.warning('BUG: node lock was not released by the moment '
                        'node info object is deleted')
            self._lock.release()

    def __str__(self):
        """Self represented as an UUID and a state."""
        parts = [self.uuid]
        if self._state:
            parts += [_('state'), self._state]
        return ' '.join(parts)

    def acquire_lock(self, blocking=True):
        """Acquire a lock on the associated node.

        Exits with success if a lock is already acquired using this NodeInfo
        object.

        :param blocking: if True, wait for lock to be acquired, otherwise
                         return immediately.
        :returns: boolean value, whether lock was acquired successfully
        """
        if self._lock.is_locked():
            return True

        LOG.debug('Attempting to acquire lock', node_info=self)
        if self._lock.acquire(blocking):
            LOG.debug('Successfully acquired lock', node_info=self)
            return True
        else:
            LOG.debug('Unable to acquire lock', node_info=self)
            return False

    def release_lock(self):
        """Release a lock on a node.

        Does nothing if lock was not acquired using this NodeInfo object.
        """
        if self._lock.is_locked():
            LOG.debug('Successfully released lock', node_info=self)
            self._lock.release()

    @property
    def version_id(self):
        """Get the version id"""
        if self._version_id is None:
            row = db.model_query(db.Node).get(self.uuid)
            if row is None:
                raise utils.NotFoundInCacheError(_('Node not found in the '
                                                   'cache'), node_info=self)
            self._version_id = row.version_id
        return self._version_id

    def _set_version_id(self, value, session):
        row = self._row(session)
        row.version_id = value
        row.save(session)
        self._version_id = value

    def _row(self, session=None):
        """Get a row from the database with self.uuid and self.version_id"""
        try:
            # race condition if version_id changed outside of this node_info
            return db.model_query(db.Node, session=session).filter_by(
                uuid=self.uuid, version_id=self.version_id).one()
        except (orm_errors.NoResultFound, orm_errors.StaleDataError):
            raise utils.NodeStateRaceCondition(node_info=self)

    def _commit(self, **fields):
        """Commit the fields into the DB."""
        LOG.debug('Committing fields: %s', fields, node_info=self)
        with db.ensure_transaction() as session:
            self._set_version_id(uuidutils.generate_uuid(), session)
            row = self._row(session)
            row.update(fields)

    def commit(self):
        """Commit current node status into the database."""
        # state and version_id are updated separately
        self._commit(started_at=self.started_at, finished_at=self.finished_at,
                     error=self.error)

    @property
    def state(self):
        """State of the node_info object."""
        if self._state is None:
            row = self._row()
            self._state = row.state
        return self._state

    def _set_state(self, value):
        self._commit(state=value)
        self._state = value

    def _get_fsm(self):
        """Get an fsm instance initialized with self.state."""
        if self._fsm is None:
            self._fsm = istate.FSM.copy(shallow=True)
        self._fsm.initialize(start_state=self.state)
        return self._fsm

    @contextlib.contextmanager
    def _fsm_ctx(self):
        fsm = self._get_fsm()
        try:
            yield fsm
        finally:
            if fsm.current_state != self.state:
                LOG.info('Updating node state: %(current)s --> %(new)s',
                         {'current': self.state, 'new': fsm.current_state},
                         node_info=self)
                self._set_state(fsm.current_state)

    def fsm_event(self, event, strict=False):
        """Update node_info.state based on a fsm.process_event(event) call.

        An AutomatonException triggers an error event.
        If strict, node_info.finished(istate.Events.error, error=str(exc))
        is called with the AutomatonException instance and a EventError raised.

        :param event: an event to process by the fsm
        :strict: whether to fail the introspection upon an invalid event
        :raises: NodeStateInvalidEvent
        """
        with self._fsm_ctx() as fsm:
            LOG.debug('Executing fsm(%(state)s).process_event(%(event)s)',
                      {'state': fsm.current_state, 'event': event},
                      node_info=self)
            try:
                fsm.process_event(event)
            except automaton_errors.NotFound as exc:
                msg = _('Invalid event: %s') % exc
                if strict:
                    LOG.error(msg, node_info=self)
                    # assuming an error event is always possible
                    self.finished(istate.Events.error, error=str(exc))
                else:
                    LOG.warning(msg, node_info=self)
                raise utils.NodeStateInvalidEvent(str(exc), node_info=self)

    @property
    def options(self):
        """Node introspection options as a dict."""
        if self._options is None:
            rows = db.model_query(db.Option).filter_by(
                uuid=self.uuid)
            self._options = {row.name: json.loads(row.value)
                             for row in rows}
        return self._options

    @property
    def attributes(self):
        """Node look up attributes as a dict."""
        if self._attributes is None:
            self._attributes = {}
            rows = db.model_query(db.Attribute).filter_by(
                node_uuid=self.uuid)
            for row in rows:
                self._attributes.setdefault(row.name, []).append(row.value)
        return self._attributes

    @property
    def ironic(self):
        """Ironic client instance."""
        if self._ironic is None:
            self._ironic = ir_utils.get_client()
        return self._ironic

    @property
    def manage_boot(self):
        """Whether to manage boot for this node."""
        return self._manage_boot

    def set_option(self, name, value):
        """Set an option for a node."""
        encoded = json.dumps(value)
        self.options[name] = value
        with db.ensure_transaction() as session:
            db.model_query(db.Option, session=session).filter_by(
                uuid=self.uuid, name=name).delete()
            db.Option(uuid=self.uuid, name=name, value=encoded).save(
                session)

    def finished(self, event, error=None):
        """Record status for this node and process a terminal transition.

        Also deletes look up attributes from the cache.

        :param event: the event to process
        :param error: error message
        """

        self.release_lock()
        self.finished_at = timeutils.utcnow()
        self.error = error

        with db.ensure_transaction() as session:
            self.fsm_event(event)
            self._commit(finished_at=self.finished_at, error=self.error)
            db.model_query(db.Attribute, session=session).filter_by(
                node_uuid=self.uuid).delete()
            db.model_query(db.Option, session=session).filter_by(
                uuid=self.uuid).delete()

    def add_attribute(self, name, value, session=None):
        """Store look up attribute for a node in the database.

        :param name: attribute name
        :param value: attribute value or list of possible values
        :param session: optional existing database session
        """
        if not isinstance(value, list):
            value = [value]

        with db.ensure_transaction(session) as session:
            for v in value:
                db.Attribute(uuid=uuidutils.generate_uuid(), name=name,
                             value=v, node_uuid=self.uuid).save(session)
            # Invalidate attributes so they're loaded on next usage
            self._attributes = None

    @classmethod
    def from_row(cls, row, ironic=None, node=None):
        """Construct NodeInfo from a database row."""
        fields = {key: row[key]
                  for key in ('uuid', 'version_id', 'state', 'started_at',
                              'finished_at', 'error', 'manage_boot')}
        return cls(ironic=ironic, node=node, **fields)

    def invalidate_cache(self):
        """Clear all cached info, so that it's reloaded next time."""
        self._options = None
        self._node = None
        self._ports = None
        self._attributes = None
        self._ironic = None
        self._fsm = None
        self._state = None
        self._version_id = None

    def node(self, ironic=None):
        """Get Ironic node object associated with the cached node record."""
        if self._node is None:
            ironic = ironic or self.ironic
            self._node = ir_utils.get_node(self.uuid, ironic=ironic)
        return self._node

    def create_ports(self, ports, ironic=None):
        """Create one or several ports for this node.

        :param ports: List of ports with all their attributes
                      e.g  [{'mac': xx, 'ip': xx, 'client_id': None},
                      {'mac': xx, 'ip': None, 'client_id': None}]
                      It also support the old style of list of macs.
                      A warning is issued if port already exists on a node.

        :param ironic: Ironic client to use instead of self.ironic
        """
        existing_macs = []
        for port in ports:
            mac = port
            extra = {}
            pxe_enabled = True
            if isinstance(port, dict):
                mac = port['mac']
                client_id = port.get('client_id')
                if client_id:
                    extra = {'client-id': client_id}
                pxe_enabled = port.get('pxe', True)

            if mac not in self.ports():
                self._create_port(mac, ironic=ironic, extra=extra,
                                  pxe_enabled=pxe_enabled)
            else:
                existing_macs.append(mac)

        if existing_macs:
            LOG.warning('Did not create ports %s as they already exist',
                        existing_macs, node_info=self)

    def ports(self, ironic=None):
        """Get Ironic port objects associated with the cached node record.

        This value is cached as well, use invalidate_cache() to clean.

        :return: dict MAC -> port object
        """
        if self._ports is None:
            ironic = ironic or self.ironic
            port_list = ironic.node.list_ports(self.uuid, limit=0, detail=True)
            self._ports = {p.address: p for p in port_list}
        return self._ports

    def _create_port(self, mac, ironic=None, **kwargs):
        ironic = ironic or self.ironic
        try:
            port = ironic.port.create(
                node_uuid=self.uuid, address=mac, **kwargs)
            LOG.info('Port %(uuid)s was created successfully, MAC: %(mac)s,'
                     'attributes: %(attrs)s',
                     {'uuid': port.uuid, 'mac': port.address,
                      'attrs': kwargs},
                     node_info=self)
        except exceptions.Conflict:
            LOG.warning('Port %s already exists, skipping',
                        mac, node_info=self)
            # NOTE(dtantsur): we didn't get port object back, so we have to
            # reload ports on next access
            self._ports = None
        else:
            self._ports[mac] = port

    def patch(self, patches, ironic=None, **kwargs):
        """Apply JSON patches to a node.

        Refreshes cached node instance.

        :param patches: JSON patches to apply
        :param ironic: Ironic client to use instead of self.ironic
        :param kwargs: Arguments to pass to ironicclient.
        :raises: ironicclient exceptions
        """
        ironic = ironic or self.ironic
        # NOTE(aarefiev): support path w/o ahead forward slash
        # as Ironic cli does
        for patch in patches:
            if patch.get('path') and not patch['path'].startswith('/'):
                patch['path'] = '/' + patch['path']

        LOG.debug('Updating node with patches %s', patches, node_info=self)
        self._node = ironic.node.update(self.uuid, patches, **kwargs)

    def patch_port(self, port, patches, ironic=None):
        """Apply JSON patches to a port.

        :param port: port object or its MAC
        :param patches: JSON patches to apply
        :param ironic: Ironic client to use instead of self.ironic
        """
        ironic = ironic or self.ironic
        ports = self.ports()
        if isinstance(port, six.string_types):
            port = ports[port]

        LOG.debug('Updating port %(mac)s with patches %(patches)s',
                  {'mac': port.address, 'patches': patches},
                  node_info=self)
        new_port = ironic.port.update(port.uuid, patches)
        ports[port.address] = new_port

    def update_properties(self, ironic=None, **props):
        """Update properties on a node.

        :param props: properties to update
        :param ironic: Ironic client to use instead of self.ironic
        """
        ironic = ironic or self.ironic
        patches = [{'op': 'add', 'path': '/properties/%s' % k, 'value': v}
                   for k, v in props.items()]
        self.patch(patches, ironic)

    def update_capabilities(self, ironic=None, **caps):
        """Update capabilities on a node.

        :param caps: capabilities to update
        :param ironic: Ironic client to use instead of self.ironic
        """
        existing = ir_utils.capabilities_to_dict(
            self.node().properties.get('capabilities'))
        existing.update(caps)
        self.update_properties(
            ironic=ironic,
            capabilities=ir_utils.dict_to_capabilities(existing))

    def add_trait(self, trait, ironic=None):
        """Add a trait to the node.

        :param trait: trait to add
        :param ironic: Ironic client to use instead of self.ironic
        """
        ironic = ironic or self.ironic
        ironic.node.add_trait(self.uuid, trait)

    def remove_trait(self, trait, ironic=None):
        """Remove a trait from the node.

        :param trait: trait to add
        :param ironic: Ironic client to use instead of self.ironic
        """
        ironic = ironic or self.ironic
        try:
            ironic.node.remove_trait(self.uuid, trait)
        except exceptions.NotFound:
            LOG.debug('Trait %s is not set, cannot remove', trait,
                      node_info=self)

    def delete_port(self, port, ironic=None):
        """Delete port.

        :param port: port object or its MAC
        :param ironic: Ironic client to use instead of self.ironic
        """
        ironic = ironic or self.ironic
        ports = self.ports()
        if isinstance(port, six.string_types):
            port = ports[port]

        ironic.port.delete(port.uuid)
        del ports[port.address]

    def get_by_path(self, path):
        """Get field value by ironic-style path (e.g. /extra/foo).

        :param path: path to a field
        :returns: field value
        :raises: KeyError if field was not found
        """
        path = path.strip('/')
        try:
            if '/' in path:
                prop, key = path.split('/', 1)
                return getattr(self.node(), prop)[key]
            else:
                return getattr(self.node(), path)
        except AttributeError:
            raise KeyError(path)

    def replace_field(self, path, func, **kwargs):
        """Replace a field on ironic node.

        :param path: path to a field as used by the ironic client
        :param func: function accepting an old value and returning a new one
        :param kwargs: if 'default' value is passed here, it will be used when
                       no existing value is found.
        :raises: KeyError if value is not found and default is not set
        :raises: everything that patch() may raise
        """
        ironic = kwargs.pop("ironic", None) or self.ironic
        try:
            value = self.get_by_path(path)
            op = 'replace'
        except KeyError:
            if 'default' in kwargs:
                value = kwargs['default']
                op = 'add'
            else:
                raise

        ref_value = copy.deepcopy(value)
        value = func(value)
        if value != ref_value:
            self.patch([{'op': op, 'path': path, 'value': value}], ironic)


def triggers_fsm_error_transition(errors=(Exception,),
                                  no_errors=(utils.NodeStateInvalidEvent,
                                             utils.NodeStateRaceCondition)):
    """Trigger an fsm error transition upon certain errors.

    It is assumed the first function arg of the decorated function is always a
    NodeInfo instance.

    :param errors: a tuple of exceptions upon which an error
                   event is triggered. Re-raised.
    :param no_errors: a tuple of exceptions that won't trigger the
                      error event.
    """
    def outer(func):
        @six.wraps(func)
        def inner(node_info, *args, **kwargs):
            ret = None
            try:
                ret = func(node_info, *args, **kwargs)
            except no_errors as exc:
                LOG.debug('Not processing error event for the '
                          'exception: %(exc)s raised by %(func)s',
                          {'exc': exc,
                           'func': reflection.get_callable_name(func)},
                          node_info=node_info)
            except errors as exc:
                with excutils.save_and_reraise_exception():
                    LOG.error('Processing the error event because of an '
                              'exception %(exc_type)s: %(exc)s raised by '
                              '%(func)s',
                              {'exc_type': type(exc), 'exc': exc,
                               'func': reflection.get_callable_name(func)},
                              node_info=node_info)
                    # an error event should be possible from all states
                    node_info.finished(istate.Events.error, error=str(exc))
            return ret
        return inner
    return outer


def fsm_event_before(event, strict=False):
    """Trigger an fsm event before the function execution.

    It is assumed the first function arg of the decorated function is always a
    NodeInfo instance.

    :param event: the event to process before the function call
    :param strict: make an invalid fsm event trigger an error event
    """
    def outer(func):
        @six.wraps(func)
        def inner(node_info, *args, **kwargs):
            LOG.debug('Processing event %(event)s before calling '
                      '%(func)s', {'event': event, 'func': func},
                      node_info=node_info)
            node_info.fsm_event(event, strict=strict)
            return func(node_info, *args, **kwargs)
        return inner
    return outer


def fsm_event_after(event, strict=False):
    """Trigger an fsm event after the function execution.

    It is assumed the first function arg of the decorated function is always a
    NodeInfo instance.

    :param event: the event to process after the function call
    :param strict: make an invalid fsm event trigger an error event
    """
    def outer(func):
        @six.wraps(func)
        def inner(node_info, *args, **kwargs):
            ret = func(node_info, *args, **kwargs)
            LOG.debug('Processing event %(event)s after calling '
                      '%(func)s', {'event': event, 'func': func},
                      node_info=node_info)
            node_info.fsm_event(event, strict=strict)
            return ret
        return inner
    return outer


def fsm_transition(event, reentrant=True, **exc_kwargs):
    """Decorate a function to perform a (non-)reentrant transition.

    If True, reentrant transition will be performed at the end of a function
    call. If False, the transition will be performed before the function call.
    The function is decorated with the triggers_fsm_error_transition decorator
    as well.

    :param event: the event to bind the transition to.
    :param reentrant: whether the transition is reentrant.
    :param exc_kwargs: passed on to the triggers_fsm_error_transition decorator
    """
    def outer(func):
        inner = triggers_fsm_error_transition(**exc_kwargs)(func)
        if not reentrant:
            return fsm_event_before(event, strict=True)(inner)
        return fsm_event_after(event)(inner)
    return outer


def release_lock(func):
    """Decorate a node_info-function to release the node_info lock.

    Assumes the first parameter of the function func is always a NodeInfo
    instance.

    """
    @six.wraps(func)
    def inner(node_info, *args, **kwargs):
        try:
            return func(node_info, *args, **kwargs)
        finally:
            # FIXME(milan) hacking the test cases to work
            # with release_lock.assert_called_once...
            if node_info._lock.is_locked():
                node_info.release_lock()
    return inner


def start_introspection(uuid, **kwargs):
    """Start the introspection of a node.

    If a node_info record exists in the DB, a start transition is used rather
    than dropping the record in order to check for the start transition
    validity in particular node state.

    :param uuid: Ironic node UUID
    :param kwargs: passed on to add_node()
    :raises: NodeStateInvalidEvent in case the start transition is invalid in
             the current node state
    :raises: NodeStateRaceCondition if a mismatch was detected between the
             node_info cache and the DB
    :returns: NodeInfo
    """
    with db.ensure_transaction():
        node_info = NodeInfo(uuid)
        # check that the start transition is possible
        try:
            node_info.fsm_event(istate.Events.start)
        except utils.NotFoundInCacheError:
            # node not found while in the fsm_event handler
            LOG.debug('Node missing in the cache; adding it now',
                      node_info=node_info)
            state = istate.States.starting
        else:
            state = node_info.state
        return add_node(uuid, state, **kwargs)


def add_node(uuid, state, manage_boot=True, **attributes):
    """Store information about a node under introspection.

    All existing information about this node is dropped.
    Empty values are skipped.

    :param uuid: Ironic node UUID
    :param state: The initial state of the node
    :param manage_boot: whether to manage boot for this node
    :param attributes: attributes known about this node (like macs, BMC etc);
                       also ironic client instance may be passed under 'ironic'
    :returns: NodeInfo
    """
    started_at = timeutils.utcnow()
    with db.ensure_transaction() as session:
        _delete_node(uuid)
        version_id = uuidutils.generate_uuid()
        db.Node(uuid=uuid, state=state, version_id=version_id,
                started_at=started_at, manage_boot=manage_boot).save(session)

        node_info = NodeInfo(uuid=uuid, state=state, started_at=started_at,
                             version_id=version_id, manage_boot=manage_boot,
                             ironic=attributes.pop('ironic', None))
        for (name, value) in attributes.items():
            if not value:
                continue
            node_info.add_attribute(name, value, session=session)

    return node_info


def delete_nodes_not_in_list(uuids):
    """Delete nodes which don't exist in Ironic node UUIDs.

    :param uuids: Ironic node UUIDs
    """
    inspector_uuids = _list_node_uuids()
    for uuid in inspector_uuids - uuids:
        LOG.warning('Node %s was deleted from Ironic, dropping from Ironic '
                    'Inspector database', uuid)
        with locking.get_lock(uuid):
            _delete_node(uuid)


def _delete_node(uuid, session=None):
    """Delete information about a node.

    :param uuid: Ironic node UUID
    :param session: optional existing database session
    """
    with db.ensure_transaction(session) as session:
        db.model_query(db.Attribute, session=session).filter_by(
            node_uuid=uuid).delete()
        for model in (db.Option, db.IntrospectionData, db.Node):
            db.model_query(model,
                           session=session).filter_by(uuid=uuid).delete()


def introspection_active():
    """Check if introspection is active for at least one node."""
    # FIXME(dtantsur): is there a better way to express it?
    return (db.model_query(db.Node.uuid).filter_by(finished_at=None).first()
            is not None)


def active_macs():
    """List all MAC's that are on introspection right now."""
    query = (db.model_query(db.Attribute.value).join(db.Node)
             .filter(db.Attribute.name == MACS_ATTRIBUTE))
    return {x.value for x in query}


def _list_node_uuids():
    """Get all nodes' uuid from cache.

    :returns: Set of nodes' uuid.
    """
    return {x.uuid for x in db.model_query(db.Node.uuid)}


def get_node(node_id, ironic=None):
    """Get node from cache.

    :param node_id: node UUID or name.
    :param ironic: optional ironic client instance
    :returns: structure NodeInfo.
    """
    if uuidutils.is_uuid_like(node_id):
        node = None
        uuid = node_id
    else:
        node = ir_utils.get_node(node_id, ironic=ironic)
        uuid = node.uuid

    row = db.model_query(db.Node).filter_by(uuid=uuid).first()
    if row is None:
        raise utils.Error(_('Could not find node %s in cache') % uuid,
                          code=404)
    return NodeInfo.from_row(row, ironic=ironic, node=node)


def find_node(**attributes):
    """Find node in cache.

    Looks up a node based on attributes in a best-match fashion.
    This function acquires a lock on a node.

    :param attributes: attributes known about this node (like macs, BMC etc)
                       also ironic client instance may be passed under 'ironic'
    :returns: structure NodeInfo with attributes ``uuid`` and ``created_at``
    :raises: Error if node is not found or multiple nodes match the attributes
    """
    ironic = attributes.pop('ironic', None)
    # NOTE(dtantsur): sorting is not required, but gives us predictability
    found = collections.Counter()

    for (name, value) in sorted(attributes.items()):
        if not value:
            LOG.debug('Empty value for attribute %s', name)
            continue
        if not isinstance(value, list):
            value = [value]

        LOG.debug('Trying to use %s of value %s for node look up',
                  name, value)
        query = db.model_query(db.Attribute.node_uuid)
        pairs = [(db.Attribute.name == name) &
                 (db.Attribute.value == v) for v in value]
        query = query.filter(six.moves.reduce(operator.or_, pairs))
        found.update(row.node_uuid for row in query.distinct().all())

    if not found:
        raise utils.NotFoundInCacheError(_(
            'Could not find a node for attributes %s') % attributes)

    most_common = found.most_common()
    LOG.debug('The following nodes match the attributes: %(attributes)s, '
              'scoring: %(most_common)s',
              {'most_common': ', '.join('%s: %d' % tpl for tpl in most_common),
               'attributes': ', '.join('%s=%s' % tpl for tpl in
                                       attributes.items())})

    # NOTE(milan) most_common is sorted, higher scores first
    highest_score = most_common[0][1]
    found = [item[0] for item in most_common if highest_score == item[1]]
    if len(found) > 1:
        raise utils.Error(_(
            'Multiple nodes match the same number of attributes '
            '%(attr)s: %(found)s')
            % {'attr': attributes, 'found': found}, code=404)

    uuid = found.pop()
    node_info = NodeInfo(uuid=uuid, ironic=ironic)
    node_info.acquire_lock()

    try:
        row = (db.model_query(db.Node.started_at, db.Node.finished_at).
               filter_by(uuid=uuid).first())

        if not row:
            raise utils.Error(_(
                'Could not find node %s in introspection cache, '
                'probably it\'s not on introspection now') % uuid, code=404)

        if row.finished_at:
            raise utils.Error(_(
                'Introspection for node %(node)s already finished on '
                '%(finish)s') % {'node': uuid, 'finish': row.finished_at})

        node_info.started_at = row.started_at
        return node_info
    except Exception:
        with excutils.save_and_reraise_exception():
            node_info.release_lock()


def clean_up():
    """Clean up the cache.

    Finish introspection for timed out nodes.

    :return: list of timed out node UUID's
    """
    timeout = CONF.timeout
    if timeout <= 0:
        return []
    threshold = timeutils.utcnow() - datetime.timedelta(seconds=timeout)
    uuids = [row.uuid for row in
             db.model_query(db.Node.uuid).filter(
                 db.Node.started_at < threshold,
                 db.Node.finished_at.is_(None)).all()]

    if not uuids:
        return []

    LOG.error('Introspection for nodes %s has timed out', uuids)
    locked_uuids = []
    for u in uuids:
        node_info = get_node(u)
        if node_info.acquire_lock(blocking=False):
            try:
                if node_info.finished_at or node_info.started_at > threshold:
                    continue
                if node_info.state != istate.States.waiting:
                    LOG.error('Something went wrong, timeout occurred '
                              'while introspection in "%s" state',
                              node_info.state,
                              node_info=node_info)
                node_info.finished(
                    istate.Events.timeout, error='Introspection timeout')
                locked_uuids.append(u)
            finally:
                node_info.release_lock()
        else:
            LOG.info('Failed to acquire lock when updating node state',
                     node_info=node_info)

    return locked_uuids


def create_node(driver, ironic=None, **attributes):
    """Create ironic node and cache it.

    * Create new node in ironic.
    * Cache it in inspector.
    * Sets node_info state to enrolling.

    :param driver: driver for Ironic node.
    :param ironic: ironic client instance.
    :param attributes: dict, additional keyword arguments to pass
                             to the ironic client on node creation.
    :return: NodeInfo, or None in case error happened.
    """
    if ironic is None:
        ironic = ir_utils.get_client()
    try:
        node = ironic.node.create(driver=driver, **attributes)
    except exceptions.InvalidAttribute as e:
        LOG.error('Failed to create new node: %s', e)
    else:
        LOG.info('Node %s was created successfully', node.uuid)
        return add_node(node.uuid, istate.States.enrolling, ironic=ironic)


def record_node(ironic=None, bmc_addresses=None, macs=None):
    """Create a cache record for a known active node.

    :param ironic: ironic client instance.
    :param bmc_addresses: list of BMC addresses.
    :param macs: list of MAC addresses.
    :return: NodeInfo
    """
    if not bmc_addresses and not macs:
        raise utils.NotFoundInCacheError(
            _("Existing node cannot be found since neither MAC addresses "
              "nor BMC addresses are present in the inventory"))

    if ironic is None:
        ironic = ir_utils.get_client()

    node = ir_utils.lookup_node(macs=macs, bmc_addresses=bmc_addresses,
                                ironic=ironic)
    if not node:
        bmc_addresses = ', '.join(bmc_addresses) if bmc_addresses else None
        macs = ', '.join(macs) if macs else None
        raise utils.NotFoundInCacheError(
            _("Existing node was not found by MAC address(es) %(macs)s "
              "and BMC address(es) %(addr)s") %
            {'macs': macs, 'addr': bmc_addresses})

    node = ironic.node.get(node, fields=['uuid', 'provision_state'])
    # TODO(dtantsur): do we want to allow updates in all states?
    if node.provision_state not in ir_utils.VALID_ACTIVE_STATES:
        raise utils.Error(_("Node %(node)s is not active, its provision "
                            "state is %(state)s") %
                          {'node': node.uuid,
                           'state': node.provision_state})

    return add_node(node.uuid, istate.States.waiting,
                    manage_boot=False, mac=macs, bmc_address=bmc_addresses)


def get_node_list(ironic=None, marker=None, limit=None):
    """Get node list from the cache.

    The list of the nodes is ordered based on the (started_at, uuid)
    attribute pair, newer items first.

    :param ironic: optional ironic client instance
    :param marker: pagination marker (an UUID or None)
    :param limit: pagination limit; None for default CONF.api_max_limit
    :returns: a list of NodeInfo instances.
    """
    if marker is not None:
        # uuid marker -> row marker for pagination
        marker = db.model_query(db.Node).get(marker)
        if marker is None:
            raise utils.Error(_('Node not found for marker: %s') % marker,
                              code=404)

    rows = db.model_query(db.Node)
    # ordered based on (started_at, uuid); newer first
    rows = db_utils.paginate_query(rows, db.Node, limit,
                                   ('started_at', 'uuid'),
                                   marker=marker, sort_dir='desc')
    return [NodeInfo.from_row(row, ironic=ironic) for row in rows]


def store_introspection_data(node_id, introspection_data, processed=True):
    """Store introspection data for this node.

    :param node_id: node UUID.
    :param introspection_data: A dictionary of introspection data
    :param processed: Specify the type of introspected data, set to False
                      indicates the data is unprocessed.
    """
    with db.ensure_transaction() as session:
        record = db.model_query(db.IntrospectionData,
                                session=session).filter_by(
            uuid=node_id, processed=processed).first()
        if record is None:
            row = db.IntrospectionData()
            row.update({'uuid': node_id, 'processed': processed,
                        'data': introspection_data})
            session.add(row)
        else:
            record.update({'data': introspection_data})
        session.flush()


def get_introspection_data(node_id, processed=True):
    """Get introspection data for this node.

    :param node_id: node UUID.
    :param processed: Specify the type of introspected data, set to False
                      indicates retrieving the unprocessed data.
    :return: A dictionary representation of intropsected data
    """
    try:
        ref = db.model_query(db.IntrospectionData).filter_by(
            uuid=node_id, processed=processed).one()
        return ref['data']
    except orm_errors.NoResultFound:
        msg = _('Introspection data not found for node %(node)s, '
                'processed=%(processed)s') % {'node': node_id,
                                              'processed': processed}
        raise utils.IntrospectionDataNotFound(msg)
