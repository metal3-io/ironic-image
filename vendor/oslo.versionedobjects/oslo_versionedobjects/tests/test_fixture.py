#    Copyright 2015 IBM Corp.
#
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

import collections
import copy
import datetime
import hashlib

import iso8601
import mock
import six

from oslo_versionedobjects import base
from oslo_versionedobjects import exception
from oslo_versionedobjects import fields
from oslo_versionedobjects import fixture
from oslo_versionedobjects import test


class MyObject(base.VersionedObject):
    fields = {'diglett': fields.IntegerField()}

    @base.remotable
    def remotable_method(self):
        pass

    @classmethod
    @base.remotable
    def remotable_classmethod(cls):
        pass

    def non_remotable_method(self):
        pass

    @classmethod
    def non_remotable_classmethod(cls):
        pass


class MyObject2(base.VersionedObject):
    pass


class MyExtraObject(base.VersionedObject):
    pass


class TestObjectComparators(test.TestCase):
    @base.VersionedObjectRegistry.register_if(False)
    class MyComparedObject(base.VersionedObject):
        fields = {'foo': fields.IntegerField(),
                  'bar': fields.IntegerField()}

    @base.VersionedObjectRegistry.register_if(False)
    class MyComparedObjectWithTZ(base.VersionedObject):
        fields = {'tzfield': fields.DateTimeField()}

    def test_compare_obj(self):
        mock_test = mock.Mock()
        mock_test.assertEqual = mock.Mock()
        my_obj = self.MyComparedObject(foo=1, bar=2)
        my_db_obj = {'foo': 1, 'bar': 2}

        fixture.compare_obj(mock_test, my_obj, my_db_obj)

        expected_calls = [(1, 1), (2, 2)]
        actual_calls = [c[0] for c in mock_test.assertEqual.call_args_list]
        for call in expected_calls:
            self.assertIn(call, actual_calls)

    def test_compare_obj_with_unset(self):
        # If the object has nothing set, and also the db object has the same
        # thing not set, it's OK.
        mock_test = mock.Mock()
        mock_test.assertEqual = mock.Mock()
        my_obj = self.MyComparedObject()
        my_db_obj = {}

        fixture.compare_obj(mock_test, my_obj, my_db_obj)

        self.assertFalse(mock_test.assertEqual.called, "assertEqual should "
                         "not have been called, there is nothing to compare.")

    def test_compare_obj_with_unset_in_obj(self):
        # If the db dict has something set, but the object doesn't, that's !=
        mock_test = mock.Mock()
        mock_test.assertEqual = mock.Mock()
        my_obj = self.MyComparedObject(foo=1)
        my_db_obj = {'foo': 1, 'bar': 2}

        self.assertRaises(AssertionError, fixture.compare_obj, mock_test,
                          my_obj, my_db_obj)

    def test_compare_obj_with_unset_in_db_dict(self):
        # If the object has something set, but the db dict doesn't, that's !=
        mock_test = mock.Mock()
        mock_test.assertEqual = mock.Mock()
        my_obj = self.MyComparedObject(foo=1, bar=2)
        my_db_obj = {'foo': 1}

        self.assertRaises(AssertionError, fixture.compare_obj, mock_test,
                          my_obj, my_db_obj)

    def test_compare_obj_with_unset_in_obj_ignored(self):
        # If the db dict has something set, but the object doesn't, but we
        # ignore that key, we are equal
        my_obj = self.MyComparedObject(foo=1)
        my_db_obj = {'foo': 1, 'bar': 2}
        ignore = ['bar']

        fixture.compare_obj(self, my_obj, my_db_obj, allow_missing=ignore)

    def test_compare_obj_with_unset_in_db_dict_ignored(self):
        # If the object has something set, but the db dict doesn't, but we
        # ignore that key, we are equal
        my_obj = self.MyComparedObject(foo=1, bar=2)
        my_db_obj = {'foo': 1}
        ignore = ['bar']

        fixture.compare_obj(self, my_obj, my_db_obj, allow_missing=ignore)

    def test_compare_obj_with_allow_missing_unequal(self):
        # If the tested key is in allow_missing, but both the obj and db_obj
        # have the value set, we should still check it for equality
        mock_test = mock.Mock()
        mock_test.assertEqual = mock.Mock()
        my_obj = self.MyComparedObject(foo=1, bar=2)
        my_db_obj = {'foo': 1, 'bar': 1}
        ignore = ['bar']

        fixture.compare_obj(mock_test, my_obj, my_db_obj,
                            allow_missing=ignore)

        expected_calls = [(1, 1), (1, 2)]
        actual_calls = [c[0] for c in mock_test.assertEqual.call_args_list]
        for call in expected_calls:
            self.assertIn(call, actual_calls)

    def test_compare_obj_with_subs(self):
        mock_test = mock.Mock()
        mock_test.assertEqual = mock.Mock()
        my_obj = self.MyComparedObject(foo=1, bar=2)
        my_db_obj = {'doo': 1, 'bar': 2}
        subs = {'foo': 'doo'}

        fixture.compare_obj(mock_test, my_obj, my_db_obj, subs=subs)

        expected_calls = [(1, 1), (2, 2)]
        actual_calls = [c[0] for c in mock_test.assertEqual.call_args_list]
        for call in expected_calls:
            self.assertIn(call, actual_calls)

    def test_compare_obj_with_allow_missing(self):
        mock_test = mock.Mock()
        mock_test.assertEqual = mock.Mock()
        my_obj = self.MyComparedObject(foo=1)
        my_db_obj = {'foo': 1, 'bar': 2}
        ignores = ['bar']

        fixture.compare_obj(mock_test, my_obj, my_db_obj,
                            allow_missing=ignores)

        mock_test.assertEqual.assert_called_once_with(1, 1)

    def test_compare_obj_with_comparators(self):
        mock_test = mock.Mock()
        mock_test.assertEqual = mock.Mock()
        comparator = mock.Mock()
        comp_dict = {'foo': comparator}
        my_obj = self.MyComparedObject(foo=1, bar=2)
        my_db_obj = {'foo': 1, 'bar': 2}

        fixture.compare_obj(mock_test, my_obj, my_db_obj,
                            comparators=comp_dict)

        comparator.assert_called_once_with(1, 1)
        mock_test.assertEqual.assert_called_once_with(2, 2)

    def test_compare_obj_with_dt(self):
        mock_test = mock.Mock()
        mock_test.assertEqual = mock.Mock()
        dt = datetime.datetime(1955, 11, 5, tzinfo=iso8601.iso8601.UTC)
        replaced_dt = dt.replace(tzinfo=None)
        my_obj = self.MyComparedObjectWithTZ(tzfield=dt)
        my_db_obj = {'tzfield': replaced_dt}

        fixture.compare_obj(mock_test, my_obj, my_db_obj)

        mock_test.assertEqual.assert_called_once_with(replaced_dt,
                                                      replaced_dt)


class FakeResource(base.VersionedObject):
    # Version 1.0: Initial version
    VERSION = '1.0'

    fields = {
        'identifier': fields.Field(fields.Integer(), default=123)
    }


class TestObjectVersionChecker(test.TestCase):
    def setUp(self):
        super(TestObjectVersionChecker, self).setUp()
        objects = [MyObject, MyObject2, ]
        self.obj_classes = {obj.__name__: [obj] for obj in objects}
        self.ovc = fixture.ObjectVersionChecker(obj_classes=self.obj_classes)

    def test_get_hashes(self):
        # Make sure get_hashes retrieves the fingerprint of all objects
        fp = 'ashketchum'
        with mock.patch.object(self.ovc, '_get_fingerprint') as mock_gf:
            mock_gf.return_value = fp
            actual = self.ovc.get_hashes()

        expected = self._generate_hashes(self.obj_classes, fp)
        self.assertEqual(expected, actual, "ObjectVersionChecker is not "
                         "getting the fingerprints of all registered "
                         "objects.")

    def test_get_hashes_with_extra_data(self):
        # Make sure get_hashes uses the extra_data_func
        fp = 'garyoak'
        mock_func = mock.MagicMock()
        with mock.patch.object(self.ovc, '_get_fingerprint') as mock_gf:
            mock_gf.return_value = fp
            actual = self.ovc.get_hashes(extra_data_func=mock_func)

        expected = self._generate_hashes(self.obj_classes, fp)
        expected_calls = [((name,), {'extra_data_func': mock_func})
                          for name in self.obj_classes.keys()]

        self.assertEqual(expected, actual, "ObjectVersionChecker is not "
                         "getting the fingerprints of all registered "
                         "objects.")

        self.assertEqual(len(expected_calls), len(mock_gf.call_args_list),
                         "get_hashes() did not call get the fingerprints of "
                         "all objects in the registry.")
        for call in expected_calls:
            self.assertIn(call, mock_gf.call_args_list,
                          "get_hashes() did not call _get_fingerprint()"
                          "correctly.")

    def test_test_hashes_none_changed(self):
        # Make sure test_hashes() generates an empty dictionary when
        # there are no objects that have changed
        fp = 'pikachu'
        hashes = self._generate_hashes(self.obj_classes, fp)

        with mock.patch.object(self.ovc, 'get_hashes') as mock_gh:
            mock_gh.return_value = hashes
            # I'm so sorry, but they have to be named this way
            actual_expected, actual_actual = self.ovc.test_hashes(hashes)

        expected_expected = expected_actual = {}

        self.assertEqual(expected_expected, actual_expected, "There are no "
                         "objects changed, so the 'expected' return value "
                         "should contain no objects.")
        self.assertEqual(expected_actual, actual_actual, "There are no "
                         "objects changed, so the 'actual' return value "
                         "should contain no objects.")

    def test_test_hashes_class_not_added(self):
        # Make sure the expected and actual values differ when a class
        # was added to the registry, but not the static dictionary
        fp = 'gyrados'
        new_classes = copy.copy(self.obj_classes)
        self._add_class(new_classes, MyExtraObject)

        expected_hashes = self._generate_hashes(self.obj_classes, fp)
        actual_hashes = self._generate_hashes(new_classes, fp)

        with mock.patch.object(self.ovc, 'get_hashes') as mock_gh:
            mock_gh.return_value = actual_hashes
            actual_exp, actual_act = self.ovc.test_hashes(expected_hashes)

        expected_expected = {MyExtraObject.__name__: None}
        expected_actual = {MyExtraObject.__name__: fp}

        self.assertEqual(expected_expected, actual_exp, "Expected hashes "
                         "should not contain the fingerprint of the class "
                         "that has not been added to the expected hash "
                         "dictionary.")
        self.assertEqual(expected_actual, actual_act, "The actual hash "
                         "should contain the class that was added to the "
                         "registry.")

    def test_test_hashes_new_fp_incorrect(self):
        # Make sure the expected and actual values differ when a fingerprint
        # was changed, but the static dictionary was not updated
        fp1 = 'beedrill'
        fp2 = 'snorlax'
        expected_hashes = self._generate_hashes(self.obj_classes, fp1)
        actual_hashes = copy.copy(expected_hashes)

        actual_hashes[MyObject.__name__] = fp2

        with mock.patch.object(self.ovc, 'get_hashes') as mock_gh:
            mock_gh.return_value = actual_hashes
            actual_exp, actual_act = self.ovc.test_hashes(expected_hashes)

        expected_expected = {MyObject.__name__: fp1}
        expected_actual = {MyObject.__name__: fp2}

        self.assertEqual(expected_expected, actual_exp, "Expected hashes "
                         "should contain the updated object with the old "
                         "hash.")
        self.assertEqual(expected_actual, actual_act, "Actual hashes "
                         "should contain the updated object with the new "
                         "hash.")

    def test_test_hashes_passes_extra_func(self):
        # Make sure that test_hashes passes the extra_func to get_hashes
        mock_extra_func = mock.Mock()

        with mock.patch.object(self.ovc, 'get_hashes') as mock_get_hashes:
            self.ovc.test_hashes({}, extra_data_func=mock_extra_func)

            mock_get_hashes.assert_called_once_with(
                extra_data_func=mock_extra_func)

    def test_get_dependency_tree(self):
        # Make sure get_dependency_tree() gets the dependencies of all
        # objects in the registry
        with mock.patch.object(self.ovc, '_get_dependencies') as mock_gd:
            self.ovc.get_dependency_tree()

        expected_calls = [(({}, MyObject),), (({}, MyObject2),)]

        self.assertEqual(2, len(mock_gd.call_args_list),
                         "get_dependency_tree() tried to get the dependencies"
                         " too many times.")

        for call in expected_calls:
            self.assertIn(call, mock_gd.call_args_list,
                          "get_dependency_tree() did not get the dependencies "
                          "of the objects correctly.")

    def test_test_relationships_none_changed(self):
        # Make sure test_relationships() generates an empty dictionary when
        # no relationships have been changed
        dep_tree = {}
        # tree will be {'MyObject': {'MyObject2': '1.0'}}
        self._add_dependency(MyObject, MyObject2, dep_tree)

        with mock.patch.object(self.ovc, 'get_dependency_tree') as mock_gdt:
            mock_gdt.return_value = dep_tree
            actual_exp, actual_act = self.ovc.test_relationships(dep_tree)

        expected_expected = expected_actual = {}

        self.assertEqual(expected_expected, actual_exp, "There are no "
                         "objects changed, so the 'expected' return value "
                         "should contain no objects.")
        self.assertEqual(expected_actual, actual_act, "There are no "
                         "objects changed, so the 'actual' return value "
                         "should contain no objects.")

    def test_test_relationships_rel_added(self):
        # Make sure expected and actual relationships differ if a
        # relationship is added to a class
        exp_tree = {}
        actual_tree = {}
        self._add_dependency(MyObject, MyObject2, exp_tree)
        self._add_dependency(MyObject, MyObject2, actual_tree)
        self._add_dependency(MyObject, MyExtraObject, actual_tree)

        with mock.patch.object(self.ovc, 'get_dependency_tree') as mock_gdt:
            mock_gdt.return_value = actual_tree
            actual_exp, actual_act = self.ovc.test_relationships(exp_tree)

        expected_expected = {'MyObject': {'MyObject2': '1.0'}}
        expected_actual = {'MyObject': {'MyObject2': '1.0',
                                        'MyExtraObject': '1.0'}}

        self.assertEqual(expected_expected, actual_exp, "The expected "
                         "relationship tree is not being built from changes "
                         "correctly.")
        self.assertEqual(expected_actual, actual_act, "The actual "
                         "relationship tree is not being built from changes "
                         "correctly.")

    def test_test_relationships_class_added(self):
        # Make sure expected and actual relationships differ if a new
        # class is added to the relationship tree
        exp_tree = {}
        actual_tree = {}
        self._add_dependency(MyObject, MyObject2, exp_tree)
        self._add_dependency(MyObject, MyObject2, actual_tree)
        self._add_dependency(MyObject2, MyExtraObject, actual_tree)

        with mock.patch.object(self.ovc, 'get_dependency_tree') as mock_gdt:
            mock_gdt.return_value = actual_tree
            actual_exp, actual_act = self.ovc.test_relationships(exp_tree)

        expected_expected = {'MyObject2': None}
        expected_actual = {'MyObject2': {'MyExtraObject': '1.0'}}

        self.assertEqual(expected_expected, actual_exp, "The expected "
                         "relationship tree is not being built from changes "
                         "correctly.")
        self.assertEqual(expected_actual, actual_act, "The actual "
                         "relationship tree is not being built from changes "
                         "correctly.")

    def test_test_compatibility_routines(self):
        # Make sure test_compatibility_routines() checks the object
        # compatibility of all objects in the registry
        del self.ovc.obj_classes[MyObject2.__name__]

        with mock.patch.object(self.ovc, '_test_object_compatibility') as toc:
            self.ovc.test_compatibility_routines()

        toc.assert_called_once_with(MyObject, manifest=None, init_args=[],
                                    init_kwargs={})

    def test_test_compatibility_routines_with_manifest(self):
        # Make sure test_compatibility_routines() uses the version manifest
        del self.ovc.obj_classes[MyObject2.__name__]
        man = {'who': 'cares'}

        with mock.patch.object(self.ovc, '_test_object_compatibility') as toc:
            with mock.patch('oslo_versionedobjects.base'
                            '.obj_tree_get_versions') as otgv:
                otgv.return_value = man
                self.ovc.test_compatibility_routines(use_manifest=True)

        otgv.assert_called_once_with(MyObject.__name__)
        toc.assert_called_once_with(MyObject, manifest=man, init_args=[],
                                    init_kwargs={})

    def test_test_compatibility_routines_with_args_kwargs(self):
        # Make sure test_compatibility_routines() uses init args/kwargs
        del self.ovc.obj_classes[MyObject2.__name__]
        init_args = {MyObject: [1]}
        init_kwargs = {MyObject: {'foo': 'bar'}}

        with mock.patch.object(self.ovc, '_test_object_compatibility') as toc:
            self.ovc.test_compatibility_routines(init_args=init_args,
                                                 init_kwargs=init_kwargs)

        toc.assert_called_once_with(MyObject, manifest=None, init_args=[1],
                                    init_kwargs={'foo': 'bar'})

    def test_test_relationships_in_order(self):
        # Make sure test_relationships_in_order() tests the relationships
        # of all objects in the registry
        with mock.patch.object(self.ovc,
                               '_test_relationships_in_order') as mock_tr:
            self.ovc.test_relationships_in_order()

        expected_calls = [((MyObject,),), ((MyObject2,),)]

        self.assertEqual(2, len(mock_tr.call_args_list),
                         "test_relationships_in_order() tested too many "
                         "relationships.")
        for call in expected_calls:
            self.assertIn(call, mock_tr.call_args_list,
                          "test_relationships_in_order() did not test the "
                          "relationships of the individual objects "
                          "correctly.")

    def test_test_relationships_in_order_positive(self):
        # Make sure a correct relationship ordering doesn't blow up
        rels = {'bellsprout': [('1.0', '1.0'), ('1.1', '1.2'),
                               ('1.3', '1.3')]}
        MyObject.obj_relationships = rels

        self.ovc._test_relationships_in_order(MyObject)

    def test_test_relationships_in_order_negative(self):
        # Make sure an out-of-order relationship does blow up
        rels = {'rattata': [('1.0', '1.0'), ('1.1', '1.2'),
                            ('1.3', '1.1')]}
        MyObject.obj_relationships = rels

        self.assertRaises(AssertionError,
                          self.ovc._test_relationships_in_order, MyObject)

    def test_find_remotable_method(self):
        # Make sure we can find a remotable method on an object
        method = self.ovc._find_remotable_method(MyObject,
                                                 MyObject.remotable_method)

        self.assertEqual(MyObject.remotable_method.original_fn,
                         method,
                         "_find_remotable_method() did not find the remotable"
                         " method of MyObject.")

    def test_find_remotable_method_classmethod(self):
        # Make sure we can find a remotable classmethod on an object
        rcm = MyObject.remotable_classmethod
        method = self.ovc._find_remotable_method(MyObject, rcm)

        expected = rcm.__get__(None, MyObject).original_fn
        self.assertEqual(expected, method, "_find_remotable_method() did not "
                         "find the remotable classmethod.")

    def test_find_remotable_method_non_remotable_method(self):
        # Make sure nothing is found when we have only a non-remotable method
        nrm = MyObject.non_remotable_method
        method = self.ovc._find_remotable_method(MyObject, nrm)

        self.assertIsNone(method, "_find_remotable_method() found a method "
                          "that isn't remotable.")

    def test_find_remotable_method_non_remotable_classmethod(self):
        # Make sure we don't find a non-remotable classmethod
        nrcm = MyObject.non_remotable_classmethod
        method = self.ovc._find_remotable_method(MyObject, nrcm)

        self.assertIsNone(method, "_find_remotable_method() found a method "
                          "that isn't remotable.")

    def test_get_fingerprint(self):
        # Make sure _get_fingerprint() generates a consistent fingerprint
        MyObject.VERSION = '1.1'
        argspec = 'vulpix'

        with mock.patch('inspect.getargspec') as mock_gas:
            mock_gas.return_value = argspec
            fp = self.ovc._get_fingerprint(MyObject.__name__)

        exp_fields = sorted(list(MyObject.fields.items()))
        exp_methods = sorted([('remotable_method', argspec),
                              ('remotable_classmethod', argspec)])
        expected_relevant_data = (exp_fields, exp_methods)
        expected_hash = hashlib.md5(six.binary_type(repr(
            expected_relevant_data).encode())).hexdigest()
        expected_fp = '%s-%s' % (MyObject.VERSION, expected_hash)

        self.assertEqual(expected_fp, fp, "_get_fingerprint() did not "
                                          "generate a correct fingerprint.")

    def test_get_fingerprint_with_child_versions(self):
        # Make sure _get_fingerprint() generates a consistent fingerprint
        # when child_versions are present
        child_versions = {'1.0': '1.0', '1.1': '1.1'}
        MyObject.VERSION = '1.1'
        MyObject.child_versions = child_versions
        argspec = 'onix'

        with mock.patch('inspect.getargspec') as mock_gas:
            mock_gas.return_value = argspec
            fp = self.ovc._get_fingerprint(MyObject.__name__)

        exp_fields = sorted(list(MyObject.fields.items()))
        exp_methods = sorted([('remotable_method', argspec),
                              ('remotable_classmethod', argspec)])
        exp_child_versions = collections.OrderedDict(sorted(
            child_versions.items()))
        exp_relevant_data = (exp_fields, exp_methods, exp_child_versions)

        expected_hash = hashlib.md5(six.binary_type(repr(
            exp_relevant_data).encode())).hexdigest()
        expected_fp = '%s-%s' % (MyObject.VERSION, expected_hash)

        self.assertEqual(expected_fp, fp, "_get_fingerprint() did not "
                                          "generate a correct fingerprint.")

    def test_get_fingerprint_with_extra_data(self):
        # Make sure _get_fingerprint() uses extra_data_func when it is
        # supplied
        class ExtraDataObj(base.VersionedObject):
            pass

        def get_data(obj_class):
            return (obj_class,)

        ExtraDataObj.VERSION = '1.1'
        argspec = 'cubone'
        self._add_class(self.obj_classes, ExtraDataObj)

        with mock.patch('inspect.getargspec') as mock_gas:
            mock_gas.return_value = argspec
            fp = self.ovc._get_fingerprint(ExtraDataObj.__name__,
                                           extra_data_func=get_data)

        exp_fields = []
        exp_methods = []
        exp_extra_data = ExtraDataObj
        exp_relevant_data = (exp_fields, exp_methods, exp_extra_data)

        expected_hash = hashlib.md5(six.binary_type(repr(
            exp_relevant_data).encode())).hexdigest()
        expected_fp = '%s-%s' % (ExtraDataObj.VERSION, expected_hash)

        self.assertEqual(expected_fp, fp, "_get_fingerprint() did not "
                                          "generate a correct fingerprint.")

    def test_get_fingerprint_with_defaulted_set(self):
        class ClassWithDefaultedSetField(base.VersionedObject):
            VERSION = 1.0
            fields = {
                'empty_default': fields.SetOfIntegersField(default=set()),
                'non_empty_default': fields.SetOfIntegersField(default={1, 2})
            }
        self._add_class(self.obj_classes, ClassWithDefaultedSetField)

        # it is expected that this hash is stable across python versions
        expected = '1.0-bcc44920f2f727eca463c6eb4fe8445b'
        actual = self.ovc._get_fingerprint(ClassWithDefaultedSetField.__name__)
        self.assertEqual(expected, actual)

    def test_get_dependencies(self):
        # Make sure _get_dependencies() generates a correct tree when parsing
        # an object
        self._add_class(self.obj_classes, MyExtraObject)
        MyObject.fields['subob'] = fields.ObjectField('MyExtraObject')
        MyExtraObject.VERSION = '1.0'
        tree = {}

        self.ovc._get_dependencies(tree, MyObject)

        expected_tree = {'MyObject': {'MyExtraObject': '1.0'}}

        self.assertEqual(expected_tree, tree, "_get_dependencies() did "
                         "not generate a correct dependency tree.")

    def test_test_object_compatibility(self):
        # Make sure _test_object_compatibility() tests obj_to_primitive()
        # on each prior version to the current version
        to_prim = mock.MagicMock(spec=callable)
        MyObject.VERSION = '1.1'
        MyObject.obj_to_primitive = to_prim

        self.ovc._test_object_compatibility(MyObject)

        expected_calls = [((), {'target_version': '1.0'}),
                          ((), {'target_version': '1.1'})]

        self.assertEqual(expected_calls, to_prim.call_args_list,
                         "_test_object_compatibility() did not test "
                         "obj_to_primitive() on the correct target versions")

    def test_test_object_compatibility_args_kwargs(self):
        # Make sure _test_object_compatibility() tests obj_to_primitive()
        # with the correct args and kwargs to init
        to_prim = mock.MagicMock(spec=callable)
        MyObject.obj_to_primitive = to_prim
        MyObject.VERSION = '1.1'
        args = [1]
        kwargs = {'foo': 'bar'}

        with mock.patch.object(MyObject, '__init__',
                               return_value=None) as mock_init:
            self.ovc._test_object_compatibility(MyObject, init_args=args,
                                                init_kwargs=kwargs)

        expected_init = ((1,), {'foo': 'bar'})
        expected_init_calls = [expected_init, expected_init]
        self.assertEqual(expected_init_calls, mock_init.call_args_list,
                         "_test_object_compatibility() did not call "
                         "__init__() properly on the object")

        expected_to_prim = [((), {'target_version': '1.0'}),
                            ((), {'target_version': '1.1'})]
        self.assertEqual(expected_to_prim, to_prim.call_args_list,
                         "_test_object_compatibility() did not test "
                         "obj_to_primitive() on the correct target versions")

    def _add_class(self, obj_classes, cls):
        obj_classes[cls.__name__] = [cls]

    def _generate_hashes(self, classes, fp):
        # Generate hashes for classes, giving fp as the fingerprint
        # for all classes
        return {cls: fp for cls in classes.keys()}

    def _add_dependency(self, parent_cls, child_cls, tree):
        # Add a dependency to the tree with the parent class holding
        # version 1.0 of the given child class
        deps = tree.get(parent_cls.__name__, {})
        deps[child_cls.__name__] = '1.0'
        tree[parent_cls.__name__] = deps


class TestVersionedObjectRegistryFixture(test.TestCase):

    primitive = {'versioned_object.name': 'FakeResource',
                 'versioned_object.namespace': 'versionedobjects',
                 'versioned_object.version': '1.0',
                 'versioned_object.data': {'identifier': 123}}

    def test_object_registered_temporarily(self):
        # Test object that has not been registered
        self.assertRaises(
            exception.UnsupportedObjectError,
            FakeResource.obj_from_primitive,
            self.primitive)

        with fixture.VersionedObjectRegistryFixture() as obj_registry:
            # Register object locally
            obj_registry.setUp()
            obj_registry.register(FakeResource)

            # Test object has now been registered
            obj = FakeResource.obj_from_primitive(
                self.primitive)
            self.assertEqual(obj.identifier, 123)
            self.assertEqual('1.0', obj.VERSION)

        # Test object that is no longer registered
        self.assertRaises(
            exception.UnsupportedObjectError,
            FakeResource.obj_from_primitive,
            self.primitive)


class TestStableObjectJsonFixture(test.TestCase):
    def test_changes_sort(self):
        @base.VersionedObjectRegistry.register_if(False)
        class TestObject(base.VersionedObject):
            fields = {'z': fields.StringField(),
                      'a': fields.StringField()}

            def obj_what_changed(self):
                return ['z', 'a']

        obj = TestObject(a='foo', z='bar')
        self.assertEqual(['z', 'a'],
                         obj.obj_to_primitive()['versioned_object.changes'])
        with fixture.StableObjectJsonFixture():
            self.assertEqual(
                ['a', 'z'],
                obj.obj_to_primitive()['versioned_object.changes'])
