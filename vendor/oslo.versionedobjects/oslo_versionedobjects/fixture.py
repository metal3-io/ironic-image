#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
"""Fixtures for writing tests for code using oslo.versionedobjects

.. note::

   This module has several extra dependencies not needed at runtime
   for production code, and therefore not installed by default. To
   ensure those dependencies are present for your tests, add
   ``oslo.versionedobjects[fixtures]`` to your list of test dependencies.

"""

from collections import OrderedDict
import copy
import datetime
import hashlib
import inspect
import logging
import mock
from oslo_utils import versionutils as vutils
import six

import fixtures
from oslo_versionedobjects import base
from oslo_versionedobjects import fields


LOG = logging.getLogger(__name__)


def compare_obj(test, obj, db_obj, subs=None, allow_missing=None,
                comparators=None):
    """Compare a VersionedObject and a dict-like database object.

    This automatically converts TZ-aware datetimes and iterates over
    the fields of the object.

    :param test: The TestCase doing the comparison
    :param obj: The VersionedObject to examine
    :param db_obj: The dict-like database object to use as reference
    :param subs: A dict of objkey=dbkey field substitutions
    :param allow_missing: A list of fields that may not be in db_obj
    :param comparators: Map of comparator functions to use for certain fields
    """

    subs = subs or {}
    allow_missing = allow_missing or []
    comparators = comparators or {}

    for key in obj.fields:
        db_key = subs.get(key, key)

        # If this is an allow_missing key and it's missing in either obj or
        # db_obj, just skip it
        if key in allow_missing:
            if key not in obj or db_key not in db_obj:
                continue

        # If the value isn't set on the object, and also isn't set on the
        # db_obj, we'll skip the value check, unset in both is equal
        if not obj.obj_attr_is_set(key) and db_key not in db_obj:
            continue
        # If it's set on the object and not on the db_obj, they aren't equal
        elif obj.obj_attr_is_set(key) and db_key not in db_obj:
            raise AssertionError(("%s (db_key: %s) is set on the object, but "
                                  "not on the db_obj, so the objects are not "
                                  "equal")
                                 % (key, db_key))
        # If it's set on the db_obj and not the object, they aren't equal
        elif not obj.obj_attr_is_set(key) and db_key in db_obj:
            raise AssertionError(("%s (db_key: %s) is set on the db_obj, but "
                                  "not on the object, so the objects are not "
                                  "equal")
                                 % (key, db_key))

        # All of the checks above have safeguarded us, so we know we will
        # get an obj_val and db_val without issue
        obj_val = getattr(obj, key)
        db_val = db_obj[db_key]
        if isinstance(obj_val, datetime.datetime):
            obj_val = obj_val.replace(tzinfo=None)

        if isinstance(db_val, datetime.datetime):
            db_val = obj_val.replace(tzinfo=None)

        if key in comparators:
            comparator = comparators[key]
            comparator(db_val, obj_val)
        else:
            test.assertEqual(db_val, obj_val)


class FakeIndirectionAPI(base.VersionedObjectIndirectionAPI):
    def __init__(self, serializer=None):
        super(FakeIndirectionAPI, self).__init__()
        self._ser = serializer or base.VersionedObjectSerializer()

    def _get_changes(self, orig_obj, new_obj):
        updates = dict()
        for name, field in new_obj.fields.items():
            if not new_obj.obj_attr_is_set(name):
                continue
            if (not orig_obj.obj_attr_is_set(name) or
                    getattr(orig_obj, name) != getattr(new_obj, name)):
                updates[name] = field.to_primitive(new_obj, name,
                                                   getattr(new_obj, name))
        return updates

    def _canonicalize_args(self, context, args, kwargs):
        args = tuple(
            [self._ser.deserialize_entity(
                context, self._ser.serialize_entity(context, arg))
             for arg in args])
        kwargs = dict(
            [(argname, self._ser.deserialize_entity(
                context, self._ser.serialize_entity(context, arg)))
             for argname, arg in kwargs.items()])
        return args, kwargs

    def object_action(self, context, objinst, objmethod, args, kwargs):
        objinst = self._ser.deserialize_entity(
            context, self._ser.serialize_entity(
                context, objinst))
        objmethod = six.text_type(objmethod)
        args, kwargs = self._canonicalize_args(context, args, kwargs)
        original = objinst.obj_clone()
        with mock.patch('oslo_versionedobjects.base.VersionedObject.'
                        'indirection_api', new=None):
            result = getattr(objinst, objmethod)(*args, **kwargs)
        updates = self._get_changes(original, objinst)
        updates['obj_what_changed'] = objinst.obj_what_changed()
        return updates, result

    def object_class_action(self, context, objname, objmethod, objver,
                            args, kwargs):
        objname = six.text_type(objname)
        objmethod = six.text_type(objmethod)
        objver = six.text_type(objver)
        args, kwargs = self._canonicalize_args(context, args, kwargs)
        cls = base.VersionedObject.obj_class_from_name(objname, objver)
        with mock.patch('oslo_versionedobjects.base.VersionedObject.'
                        'indirection_api', new=None):
            result = getattr(cls, objmethod)(context, *args, **kwargs)
        return (base.VersionedObject.obj_from_primitive(
            result.obj_to_primitive(target_version=objver),
            context=context)
            if isinstance(result, base.VersionedObject) else result)

    def object_class_action_versions(self, context, objname, objmethod,
                                     object_versions, args, kwargs):
        objname = six.text_type(objname)
        objmethod = six.text_type(objmethod)
        object_versions = {six.text_type(o): six.text_type(v)
                           for o, v in object_versions.items()}
        args, kwargs = self._canonicalize_args(context, args, kwargs)
        objver = object_versions[objname]
        cls = base.VersionedObject.obj_class_from_name(objname, objver)
        with mock.patch('oslo_versionedobjects.base.VersionedObject.'
                        'indirection_api', new=None):
            result = getattr(cls, objmethod)(context, *args, **kwargs)
        return (base.VersionedObject.obj_from_primitive(
            result.obj_to_primitive(target_version=objver),
            context=context)
            if isinstance(result, base.VersionedObject) else result)

    def object_backport(self, context, objinst, target_version):
        raise Exception('not supported')


class IndirectionFixture(fixtures.Fixture):
    def __init__(self, indirection_api=None):
        self.indirection_api = indirection_api or FakeIndirectionAPI()

    def setUp(self):
        super(IndirectionFixture, self).setUp()
        self.useFixture(fixtures.MonkeyPatch(
            'oslo_versionedobjects.base.VersionedObject.indirection_api',
            self.indirection_api))


class ObjectHashMismatch(Exception):
    def __init__(self, expected, actual):
        self.expected = expected
        self.actual = actual

    def __str__(self):
        return 'Hashes have changed for %s' % (
            ','.join(set(self.expected.keys() + self.actual.keys())))


class ObjectVersionChecker(object):
    def __init__(self, obj_classes=base.VersionedObjectRegistry.obj_classes()):
        self.obj_classes = obj_classes

    def _find_remotable_method(self, cls, thing, parent_was_remotable=False):
        """Follow a chain of remotable things down to the original function."""
        if isinstance(thing, classmethod):
            return self._find_remotable_method(cls, thing.__get__(None, cls))
        elif (inspect.ismethod(thing) or
              inspect.isfunction(thing)) and hasattr(thing, 'remotable'):
            return self._find_remotable_method(cls, thing.original_fn,
                                               parent_was_remotable=True)
        elif parent_was_remotable:
            # We must be the first non-remotable thing underneath a stack of
            # remotable things (i.e. the actual implementation method)
            return thing
        else:
            # This means the top-level thing never hit a remotable layer
            return None

    def _get_fingerprint(self, obj_name, extra_data_func=None):
        obj_class = self.obj_classes[obj_name][0]
        obj_fields = list(obj_class.fields.items())
        obj_fields.sort()
        methods = []
        for name in dir(obj_class):
            thing = getattr(obj_class, name)
            if inspect.ismethod(thing) or inspect.isfunction(thing) \
               or isinstance(thing, classmethod):
                method = self._find_remotable_method(obj_class, thing)
                if method:
                    methods.append((name, inspect.getargspec(method)))
        methods.sort()
        # NOTE(danms): Things that need a version bump are any fields
        # and their types, or the signatures of any remotable methods.
        # Of course, these are just the mechanical changes we can detect,
        # but many other things may require a version bump (method behavior
        # and return value changes, for example).
        if hasattr(obj_class, 'child_versions'):
            relevant_data = (obj_fields, methods,
                             OrderedDict(
                                 sorted(obj_class.child_versions.items())))
        else:
            relevant_data = (obj_fields, methods)

        if extra_data_func:
            relevant_data += extra_data_func(obj_class)

        fingerprint = '%s-%s' % (obj_class.VERSION, hashlib.md5(
            six.binary_type(repr(relevant_data).encode())).hexdigest())
        return fingerprint

    def get_hashes(self, extra_data_func=None):
        """Return a dict of computed object hashes.

        :param extra_data_func: a function that is given the object class
                                which gathers more relevant data about the
                                class that is needed in versioning. Returns
                                a tuple containing the extra data bits.
        """

        fingerprints = {}
        for obj_name in sorted(self.obj_classes):
            fingerprints[obj_name] = self._get_fingerprint(
                obj_name, extra_data_func=extra_data_func)
        return fingerprints

    def test_hashes(self, expected_hashes, extra_data_func=None):
        fingerprints = self.get_hashes(extra_data_func=extra_data_func)

        stored = set(expected_hashes.items())
        computed = set(fingerprints.items())
        changed = stored.symmetric_difference(computed)
        expected = {}
        actual = {}
        for name, hash in changed:
            expected[name] = expected_hashes.get(name)
            actual[name] = fingerprints.get(name)

        return expected, actual

    def _get_dependencies(self, tree, obj_class):
        obj_name = obj_class.obj_name()
        if obj_name in tree:
            return

        for name, field in obj_class.fields.items():
            if isinstance(field._type, fields.Object):
                sub_obj_name = field._type._obj_name
                sub_obj_class = self.obj_classes[sub_obj_name][0]
                self._get_dependencies(tree, sub_obj_class)
                tree.setdefault(obj_name, {})
                tree[obj_name][sub_obj_name] = sub_obj_class.VERSION

    def get_dependency_tree(self):
        tree = {}
        for obj_name in self.obj_classes.keys():
            self._get_dependencies(tree, self.obj_classes[obj_name][0])
        return tree

    def test_relationships(self, expected_tree):
        actual_tree = self.get_dependency_tree()

        stored = set([(x, str(y)) for x, y in expected_tree.items()])
        computed = set([(x, str(y)) for x, y in actual_tree.items()])
        changed = stored.symmetric_difference(computed)
        expected = {}
        actual = {}
        for name, deps in changed:
            expected[name] = expected_tree.get(name)
            actual[name] = actual_tree.get(name)

        return expected, actual

    def _test_object_compatibility(self, obj_class, manifest=None,
                                   init_args=None, init_kwargs=None):
        init_args = init_args or []
        init_kwargs = init_kwargs or {}
        version = vutils.convert_version_to_tuple(obj_class.VERSION)
        kwargs = {'version_manifest': manifest} if manifest else {}
        for n in range(version[1] + 1):
            test_version = '%d.%d' % (version[0], n)
            # Run the test with OS_DEBUG=True to see this.
            LOG.debug('testing obj: %s version: %s' %
                      (obj_class.obj_name(), test_version))
            kwargs['target_version'] = test_version
            obj_class(*init_args, **init_kwargs).obj_to_primitive(**kwargs)

    def test_compatibility_routines(self, use_manifest=False, init_args=None,
                                    init_kwargs=None):
        """Test obj_make_compatible() on all object classes.

        :param use_manifest: a boolean that determines if the version
                             manifest should be passed to obj_make_compatible
        :param init_args: a dictionary of the format {obj_class: [arg1, arg2]}
                          that will be used to pass arguments to init on the
                          given obj_class. If no args are needed, the
                          obj_class does not need to be added to the dict
        :param init_kwargs: a dictionary of the format
                            {obj_class: {'kwarg1': val1}} that will be used to
                            pass kwargs to init on the given obj_class. If no
                            kwargs are needed, the obj_class does not need to
                            be added to the dict
        """
        # Iterate all object classes and verify that we can run
        # obj_make_compatible with every older version than current.
        # This doesn't actually test the data conversions, but it at least
        # makes sure the method doesn't blow up on something basic like
        # expecting the wrong version format.
        init_args = init_args or {}
        init_kwargs = init_kwargs or {}
        for obj_name in self.obj_classes:
            obj_classes = self.obj_classes[obj_name]
            if use_manifest:
                manifest = base.obj_tree_get_versions(obj_name)
            else:
                manifest = None

            for obj_class in obj_classes:
                args_for_init = init_args.get(obj_class, [])
                kwargs_for_init = init_kwargs.get(obj_class, {})
                self._test_object_compatibility(obj_class, manifest=manifest,
                                                init_args=args_for_init,
                                                init_kwargs=kwargs_for_init)

    def _test_relationships_in_order(self, obj_class):
        for field, versions in obj_class.obj_relationships.items():
            last_my_version = (0, 0)
            last_child_version = (0, 0)
            for my_version, child_version in versions:
                _my_version = vutils.convert_version_to_tuple(my_version)
                _ch_version = vutils.convert_version_to_tuple(child_version)
                if not (last_my_version < _my_version and
                        last_child_version <= _ch_version):
                    raise AssertionError(('Object %s relationship %s->%s for '
                                          'field %s is out of order') % (
                                              obj_class.obj_name(),
                                              my_version, child_version,
                                              field))
                last_my_version = _my_version
                last_child_version = _ch_version

    def test_relationships_in_order(self):
        # Iterate all object classes and verify that we can run
        # obj_make_compatible with every older version than current.
        # This doesn't actually test the data conversions, but it at least
        # makes sure the method doesn't blow up on something basic like
        # expecting the wrong version format.
        for obj_name in self.obj_classes:
            obj_classes = self.obj_classes[obj_name]
            for obj_class in obj_classes:
                self._test_relationships_in_order(obj_class)


class VersionedObjectRegistryFixture(fixtures.Fixture):
    """Use a VersionedObjectRegistry as a temp registry pattern fixture.

    The pattern solution is to backup the object registry, register
    a class locally, and then restore the original registry. This could be
    used for test objects that do not need to be registered permanently but
    will have calls which lookup registration.
    """

    def setUp(self):
        super(VersionedObjectRegistryFixture, self).setUp()
        self._base_test_obj_backup = copy.deepcopy(
            base.VersionedObjectRegistry._registry._obj_classes)
        self.addCleanup(self._restore_obj_registry)

    @staticmethod
    def register(cls_name):
        base.VersionedObjectRegistry.register(cls_name)

    def _restore_obj_registry(self):
        base.VersionedObjectRegistry._registry._obj_classes = \
            self._base_test_obj_backup


class StableObjectJsonFixture(fixtures.Fixture):
    """Fixture that makes sure we get stable JSON object representations.

    Since objects contain things like set(), which can't be converted to
    JSON, we have some situations where the representation isn't fully
    deterministic. This doesn't matter at all at runtime, but does to
    unit tests that try to assert things at a low level.

    This fixture mocks the obj_to_primitive() call and makes sure to
    sort the list of changed fields (which came from a set) before
    returning it to the caller.
    """
    def __init__(self):
        self._original_otp = base.VersionedObject.obj_to_primitive

    def setUp(self):
        super(StableObjectJsonFixture, self).setUp()

        def _doit(obj, *args, **kwargs):
            result = self._original_otp(obj, *args, **kwargs)
            changes_key = obj._obj_primitive_key('changes')
            if changes_key in result:
                result[changes_key].sort()
            return result

        self.useFixture(fixtures.MonkeyPatch(
            'oslo_versionedobjects.base.VersionedObject.obj_to_primitive',
            _doit))
