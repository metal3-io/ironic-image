# Copyright 2015 Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""Support for introspection rules."""

import jsonpath_rw as jsonpath
import jsonschema
from oslo_db import exception as db_exc
from oslo_utils import timeutils
from oslo_utils import uuidutils
import six
from sqlalchemy import orm

from ironic_inspector.common.i18n import _
from ironic_inspector import db
from ironic_inspector.plugins import base as plugins_base
from ironic_inspector import utils


LOG = utils.getProcessingLogger(__name__)
_CONDITIONS_SCHEMA = None
_ACTIONS_SCHEMA = None


def conditions_schema():
    global _CONDITIONS_SCHEMA
    if _CONDITIONS_SCHEMA is None:
        condition_plugins = [x.name for x in
                             plugins_base.rule_conditions_manager()]
        _CONDITIONS_SCHEMA = {
            "title": "Inspector rule conditions schema",
            "type": "array",
            # we can have rules that always apply
            "minItems": 0,
            "items": {
                "type": "object",
                # field might become optional in the future, but not right now
                "required": ["op", "field"],
                "properties": {
                    "op": {
                        "description": "condition operator",
                        "enum": condition_plugins
                    },
                    "field": {
                        "description": "JSON path to field for matching",
                        "type": "string"
                    },
                    "multiple": {
                        "description": "how to treat multiple values",
                        "enum": ["all", "any", "first"]
                    },
                    "invert": {
                        "description": "whether to invert the result",
                        "type": "boolean"
                    },
                },
                # other properties are validated by plugins
                "additionalProperties": True
            }
        }

    return _CONDITIONS_SCHEMA


def actions_schema():
    global _ACTIONS_SCHEMA
    if _ACTIONS_SCHEMA is None:
        action_plugins = [x.name for x in
                          plugins_base.rule_actions_manager()]
        _ACTIONS_SCHEMA = {
            "title": "Inspector rule actions schema",
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["action"],
                "properties": {
                    "action": {
                        "description": "action to take",
                        "enum": action_plugins
                    },
                },
                # other properties are validated by plugins
                "additionalProperties": True
            }
        }

    return _ACTIONS_SCHEMA


class IntrospectionRule(object):
    """High-level class representing an introspection rule."""

    def __init__(self, uuid, conditions, actions, description):
        """Create rule object from database data."""
        self._uuid = uuid
        self._conditions = conditions
        self._actions = actions
        self._description = description

    def as_dict(self, short=False):
        result = {
            'uuid': self._uuid,
            'description': self._description,
        }

        if not short:
            result['conditions'] = [c.as_dict() for c in self._conditions]
            result['actions'] = [a.as_dict() for a in self._actions]

        return result

    @property
    def description(self):
        return self._description or self._uuid

    def check_conditions(self, node_info, data):
        """Check if conditions are true for a given node.

        :param node_info: a NodeInfo object
        :param data: introspection data
        :returns: True if conditions match, otherwise False
        """
        LOG.debug('Checking rule "%s"', self.description,
                  node_info=node_info, data=data)
        ext_mgr = plugins_base.rule_conditions_manager()
        for cond in self._conditions:
            scheme, path = _parse_path(cond.field)

            if scheme == 'node':
                source_data = node_info.node().to_dict()
            elif scheme == 'data':
                source_data = data

            field_values = jsonpath.parse(path).find(source_data)
            field_values = [x.value for x in field_values]
            cond_ext = ext_mgr[cond.op].obj

            if not field_values:
                if cond_ext.ALLOW_NONE:
                    LOG.debug('Field with JSON path %s was not found in data',
                              cond.field, node_info=node_info, data=data)
                    field_values = [None]
                else:
                    LOG.info('Field with JSON path %(path)s was not found '
                             'in data, rule "%(rule)s" will not '
                             'be applied',
                             {'path': cond.field, 'rule': self.description},
                             node_info=node_info, data=data)
                    return False

            for value in field_values:
                result = cond_ext.check(node_info, value, cond.params)
                if cond.invert:
                    result = not result

                if (cond.multiple == 'first'
                        or (cond.multiple == 'all' and not result)
                        or (cond.multiple == 'any' and result)):
                    break

            if not result:
                LOG.info('Rule "%(rule)s" will not be applied: condition '
                         '%(field)s %(op)s %(params)s failed',
                         {'rule': self.description, 'field': cond.field,
                          'op': cond.op, 'params': cond.params},
                         node_info=node_info, data=data)
                return False

        LOG.info('Rule "%s" will be applied', self.description,
                 node_info=node_info, data=data)
        return True

    def apply_actions(self, node_info, data=None):
        """Run actions on a node.

        :param node_info: NodeInfo instance
        :param data: introspection data
        """
        LOG.debug('Running actions for rule "%s"', self.description,
                  node_info=node_info, data=data)

        ext_mgr = plugins_base.rule_actions_manager()
        for act in self._actions:
            ext = ext_mgr[act.action].obj

            for formatted_param in ext.FORMATTED_PARAMS:
                try:
                    initial = act.params[formatted_param]
                except KeyError:
                    # Ignore parameter that wasn't given.
                    continue
                else:
                    act.params[formatted_param] = _format_value(initial, data)

            LOG.debug('Running action `%(action)s %(params)s`',
                      {'action': act.action, 'params': act.params},
                      node_info=node_info, data=data)
            ext.apply(node_info, act.params)

        LOG.debug('Successfully applied actions',
                  node_info=node_info, data=data)


def _format_value(value, data):
    """Apply parameter formatting to a value.

    Format strings with the values from `data`. If `value` is a dict or
    list, any string members (and any nested string members) will also be
    formatted recursively. This includes both keys and values for dicts.

    :param value: The string to format, or container whose members to
                  format.
    :param data: Introspection data.
    :returns: `value`, formatted with the parameters from `data`.
    """
    if isinstance(value, six.string_types):
        # NOTE(aarefiev): verify provided value with introspection
        # data format specifications.
        # TODO(aarefiev): simple verify on import rule time.
        try:
            return value.format(data=data)
        except KeyError as e:
            raise utils.Error(_('Invalid formatting variable key '
                                'provided in value %(val)s: %(e)s'),
                              {'val': value, 'e': e}, data=data)
    elif isinstance(value, dict):
        return {_format_value(k, data): _format_value(v, data)
                for k, v in six.iteritems(value)}
    elif isinstance(value, list):
        return [_format_value(v, data) for v in value]
    else:
        # Assume this is a 'primitive' value.
        return value


def _parse_path(path):
    """Parse path, extract scheme and path.

     Parse path with 'node' and 'data' scheme, which links on
     introspection data and node info respectively. If scheme is
     missing in path, default is 'data'.

    :param path: data or node path
    :return: tuple (scheme, path)
    """
    try:
        index = path.index('://')
    except ValueError:
        scheme = 'data'
        path = path
    else:
        scheme = path[:index]
        path = path[index + 3:]
    return scheme, path


def _validate_conditions(conditions_json):
    """Validates conditions from jsonschema.

    :returns: a list of conditions.
    """
    try:
        jsonschema.validate(conditions_json, conditions_schema())
    except jsonschema.ValidationError as exc:
        raise utils.Error(_('Validation failed for conditions: %s') % exc)

    cond_mgr = plugins_base.rule_conditions_manager()
    conditions = []
    reserved_params = {'op', 'field', 'multiple', 'invert'}
    for cond_json in conditions_json:
        field = cond_json['field']

        scheme, path = _parse_path(field)

        if scheme not in ('node', 'data'):
            raise utils.Error(_('Unsupported scheme for field: %s, valid '
                                'values are node:// or data://') % scheme)
        # verify field as JSON path
        try:
            jsonpath.parse(path)
        except Exception as exc:
            raise utils.Error(_('Unable to parse field JSON path %(field)s: '
                                '%(error)s') % {'field': field, 'error': exc})

        plugin = cond_mgr[cond_json['op']].obj
        params = {k: v for k, v in cond_json.items()
                  if k not in reserved_params}
        try:
            plugin.validate(params)
        except ValueError as exc:
            raise utils.Error(_('Invalid parameters for operator %(op)s: '
                                '%(error)s') %
                              {'op': cond_json['op'], 'error': exc})

        conditions.append((cond_json['field'],
                           cond_json['op'],
                           cond_json.get('multiple', 'any'),
                           cond_json.get('invert', False),
                           params))
    return conditions


def _validate_actions(actions_json):
    """Validates actions from jsonschema.

    :returns: a list of actions.
    """
    try:
        jsonschema.validate(actions_json, actions_schema())
    except jsonschema.ValidationError as exc:
        raise utils.Error(_('Validation failed for actions: %s') % exc)

    act_mgr = plugins_base.rule_actions_manager()
    actions = []
    for action_json in actions_json:
        plugin = act_mgr[action_json['action']].obj
        params = {k: v for k, v in action_json.items() if k != 'action'}
        try:
            plugin.validate(params)
        except ValueError as exc:
            raise utils.Error(_('Invalid parameters for action %(act)s: '
                                '%(error)s') %
                              {'act': action_json['action'], 'error': exc})

        actions.append((action_json['action'], params))
    return actions


def create(conditions_json, actions_json, uuid=None,
           description=None):
    """Create a new rule in database.

    :param conditions_json: list of dicts with the following keys:
                            * op - operator
                            * field - JSON path to field to compare
                            Other keys are stored as is.
    :param actions_json: list of dicts with the following keys:
                         * action - action type
                         Other keys are stored as is.
    :param uuid: rule UUID, will be generated if empty
    :param description: human-readable rule description
    :returns: new IntrospectionRule object
    :raises: utils.Error on failure
    """
    uuid = uuid or uuidutils.generate_uuid()
    LOG.debug('Creating rule %(uuid)s with description "%(descr)s", '
              'conditions %(conditions)s and actions %(actions)s',
              {'uuid': uuid, 'descr': description,
               'conditions': conditions_json, 'actions': actions_json})

    conditions = _validate_conditions(conditions_json)
    actions = _validate_actions(actions_json)

    try:
        with db.ensure_transaction() as session:
            rule = db.Rule(uuid=uuid, description=description,
                           disabled=False, created_at=timeutils.utcnow())

            for field, op, multiple, invert, params in conditions:
                rule.conditions.append(db.RuleCondition(op=op,
                                                        field=field,
                                                        multiple=multiple,
                                                        invert=invert,
                                                        params=params))

            for action, params in actions:
                rule.actions.append(db.RuleAction(action=action,
                                                  params=params))

            rule.save(session)
    except db_exc.DBDuplicateEntry as exc:
        LOG.error('Database integrity error %s when '
                  'creating a rule', exc)
        raise utils.Error(_('Rule with UUID %s already exists') % uuid,
                          code=409)

    LOG.info('Created rule %(uuid)s with description "%(descr)s"',
             {'uuid': uuid, 'descr': description})
    return IntrospectionRule(uuid=uuid,
                             conditions=rule.conditions,
                             actions=rule.actions,
                             description=description)


def get(uuid):
    """Get a rule by its UUID."""
    try:
        rule = db.model_query(db.Rule).filter_by(uuid=uuid).one()
    except orm.exc.NoResultFound:
        raise utils.Error(_('Rule %s was not found') % uuid, code=404)

    return IntrospectionRule(uuid=rule.uuid, actions=rule.actions,
                             conditions=rule.conditions,
                             description=rule.description)


def get_all():
    """List all rules."""
    query = db.model_query(db.Rule).order_by(db.Rule.created_at)
    return [IntrospectionRule(uuid=rule.uuid, actions=rule.actions,
                              conditions=rule.conditions,
                              description=rule.description)
            for rule in query]


def delete(uuid):
    """Delete a rule by its UUID."""
    with db.ensure_transaction() as session:
        db.model_query(db.RuleAction,
                       session=session).filter_by(rule=uuid).delete()
        db.model_query(db.RuleCondition,
                       session=session) .filter_by(rule=uuid).delete()
        count = (db.model_query(db.Rule, session=session)
                 .filter_by(uuid=uuid).delete())
        if not count:
            raise utils.Error(_('Rule %s was not found') % uuid, code=404)

    LOG.info('Introspection rule %s was deleted', uuid)


def delete_all():
    """Delete all rules."""
    with db.ensure_transaction() as session:
        db.model_query(db.RuleAction, session=session).delete()
        db.model_query(db.RuleCondition, session=session).delete()
        db.model_query(db.Rule, session=session).delete()

    LOG.info('All introspection rules were deleted')


def apply(node_info, data):
    """Apply rules to a node."""
    rules = get_all()
    if not rules:
        LOG.debug('No custom introspection rules to apply',
                  node_info=node_info, data=data)
        return

    LOG.debug('Applying custom introspection rules',
              node_info=node_info, data=data)

    to_apply = []
    for rule in rules:
        if rule.check_conditions(node_info, data):
            to_apply.append(rule)

    if to_apply:
        LOG.debug('Running actions', node_info=node_info, data=data)
        for rule in to_apply:
            rule.apply_actions(node_info, data=data)
    else:
        LOG.debug('No actions to apply', node_info=node_info, data=data)

    LOG.info('Successfully applied custom introspection rules',
             node_info=node_info, data=data)
