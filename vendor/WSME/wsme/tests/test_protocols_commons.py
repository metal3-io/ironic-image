# encoding=utf8

import datetime
import unittest

from wsme.api import FunctionArgument, FunctionDefinition
from wsme.rest.args import from_param, from_params, args_from_args
from wsme.exc import InvalidInput

from wsme.types import UserType, Unset, ArrayType, DictType, Base


class MyBaseType(Base):
    test = str


class MyUserType(UserType):
    basetype = str


class DictBasedUserType(UserType):
    basetype = DictType(int, int)


class TestProtocolsCommons(unittest.TestCase):
    def test_from_param_date(self):
        assert from_param(datetime.date, '2008-02-28') == \
            datetime.date(2008, 2, 28)

    def test_from_param_time(self):
        assert from_param(datetime.time, '12:14:56') == \
            datetime.time(12, 14, 56)

    def test_from_param_datetime(self):
        assert from_param(datetime.datetime, '2009-12-23T12:14:56') == \
            datetime.datetime(2009, 12, 23, 12, 14, 56)

    def test_from_param_usertype(self):
        assert from_param(MyUserType(), 'test') == 'test'

    def test_from_params_empty(self):
        assert from_params(str, {}, '', set()) is Unset

    def test_from_params_native_array(self):
        class params(dict):
            def getall(self, path):
                return ['1', '2']
        p = params({'a': []})
        assert from_params(ArrayType(int), p, 'a', set()) == [1, 2]

    def test_from_params_empty_array(self):
        assert from_params(ArrayType(int), {}, 'a', set()) is Unset

    def test_from_params_dict(self):
        value = from_params(
            DictType(int, str),
            {'a[2]': 'a2', 'a[3]': 'a3'},
            'a',
            set()
        )
        assert value == {2: 'a2', 3: 'a3'}, value

    def test_from_params_dict_unset(self):
        assert from_params(DictType(int, str), {}, 'a', set()) is Unset

    def test_from_params_usertype(self):
        value = from_params(
            DictBasedUserType(),
            {'a[2]': '2'},
            'a',
            set()
        )
        self.assertEqual(value, {2: 2})

    def test_args_from_args_usertype(self):

        class FakeType(UserType):
            name = 'fake-type'
            basetype = int

        fake_type = FakeType()
        fd = FunctionDefinition(FunctionDefinition)
        fd.arguments.append(FunctionArgument('fake-arg', fake_type, True, 0))

        new_args = args_from_args(fd, [1], {})
        self.assertEqual([1], new_args[0])

        # can't convert str to int
        try:
            args_from_args(fd, ['invalid-argument'], {})
        except InvalidInput as e:
            assert fake_type.name in str(e)
        else:
            self.fail('Should have thrown an InvalidInput')

    def test_args_from_args_custom_exc(self):

        class FakeType(UserType):
            name = 'fake-type'
            basetype = int

            def validate(self, value):
                if value < 10:
                    raise ValueError('should be greater than 10')

            def frombasetype(self, value):
                self.validate(value)

        fake_type = FakeType()
        fd = FunctionDefinition(FunctionDefinition)
        fd.arguments.append(FunctionArgument('fake-arg', fake_type, True, 0))

        try:
            args_from_args(fd, [9], {})
        except InvalidInput as e:
            assert fake_type.name in str(e)
            assert 'Error: should be greater than 10' in str(e)
        else:
            self.fail('Should have thrown an InvalidInput')

    def test_args_from_args_array_type(self):
        fake_type = ArrayType(MyBaseType)
        fd = FunctionDefinition(FunctionDefinition)
        fd.arguments.append(FunctionArgument('fake-arg', fake_type, True, []))
        try:
            args_from_args(fd, [['invalid-argument']], {})
        except InvalidInput as e:
            assert ArrayType.__name__ in str(e)
        else:
            self.fail('Should have thrown an InvalidInput')


class ArgTypeConversion(unittest.TestCase):

    def test_int_zero(self):
        self.assertEqual(0, from_param(int, 0))
        self.assertEqual(0, from_param(int, '0'))

    def test_int_nonzero(self):
        self.assertEqual(1, from_param(int, 1))
        self.assertEqual(1, from_param(int, '1'))

    def test_int_none(self):
        self.assertEqual(None, from_param(int, None))

    def test_float_zero(self):
        self.assertEqual(0.0, from_param(float, 0))
        self.assertEqual(0.0, from_param(float, 0.0))
        self.assertEqual(0.0, from_param(float, '0'))
        self.assertEqual(0.0, from_param(float, '0.0'))

    def test_float_nonzero(self):
        self.assertEqual(1.0, from_param(float, 1))
        self.assertEqual(1.0, from_param(float, 1.0))
        self.assertEqual(1.0, from_param(float, '1'))
        self.assertEqual(1.0, from_param(float, '1.0'))

    def test_float_none(self):
        self.assertEqual(None, from_param(float, None))
