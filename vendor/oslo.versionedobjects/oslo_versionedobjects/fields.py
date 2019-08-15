#    Copyright 2013 Red Hat, Inc.
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

import abc
# TODO(smcginnis) update this once six has support for collections.abc
# (https://github.com/benjaminp/six/pull/241) or clean up once we drop py2.7.
try:
    from collections.abc import Iterable
    from collections.abc import Mapping
except ImportError:
    from collections import Iterable
    from collections import Mapping
import datetime
from distutils import versionpredicate
import re
import uuid
import warnings

import copy
import iso8601
import netaddr
from oslo_utils import strutils
from oslo_utils import timeutils
import six

from oslo_versionedobjects._i18n import _
from oslo_versionedobjects import _utils
from oslo_versionedobjects import exception


class KeyTypeError(TypeError):
    def __init__(self, expected, value):
        super(KeyTypeError, self).__init__(
            _('Key %(key)s must be of type %(expected)s not %(actual)s'
              ) % {'key': repr(value),
                   'expected': expected.__name__,
                   'actual': value.__class__.__name__,
                   })


class ElementTypeError(TypeError):
    def __init__(self, expected, key, value):
        super(ElementTypeError, self).__init__(
            _('Element %(key)s:%(val)s must be of type %(expected)s'
              ' not %(actual)s'
              ) % {'key': key,
                   'val': repr(value),
                   'expected': expected,
                   'actual': value.__class__.__name__,
                   })


@six.add_metaclass(abc.ABCMeta)
class AbstractFieldType(object):
    @abc.abstractmethod
    def coerce(self, obj, attr, value):
        """This is called to coerce (if possible) a value on assignment.

        This method should convert the value given into the designated type,
        or throw an exception if this is not possible.

        :param:obj: The VersionedObject on which an attribute is being set
        :param:attr: The name of the attribute being set
        :param:value: The value being set
        :returns: A properly-typed value
        """
        pass

    @abc.abstractmethod
    def from_primitive(self, obj, attr, value):
        """This is called to deserialize a value.

        This method should deserialize a value from the form given by
        to_primitive() to the designated type.

        :param:obj: The VersionedObject on which the value is to be set
        :param:attr: The name of the attribute which will hold the value
        :param:value: The serialized form of the value
        :returns: The natural form of the value
        """
        pass

    @abc.abstractmethod
    def to_primitive(self, obj, attr, value):
        """This is called to serialize a value.

        This method should serialize a value to the form expected by
        from_primitive().

        :param:obj: The VersionedObject on which the value is set
        :param:attr: The name of the attribute holding the value
        :param:value: The natural form of the value
        :returns: The serialized form of the value
        """
        pass

    @abc.abstractmethod
    def describe(self):
        """Returns a string describing the type of the field."""
        pass

    @abc.abstractmethod
    def stringify(self, value):
        """Returns a short stringified version of a value."""
        pass


class FieldType(AbstractFieldType):
    @staticmethod
    def coerce(obj, attr, value):
        return value

    @staticmethod
    def from_primitive(obj, attr, value):
        return value

    @staticmethod
    def to_primitive(obj, attr, value):
        return value

    def describe(self):
        return self.__class__.__name__

    def stringify(self, value):
        return str(value)

    def get_schema(self):
        raise NotImplementedError()


class UnspecifiedDefault(object):
    pass


class Field(object):
    def __init__(self, field_type, nullable=False,
                 default=UnspecifiedDefault, read_only=False):
        self._type = field_type
        self._nullable = nullable
        self._default = default
        self._read_only = read_only

    def __repr__(self):
        if isinstance(self._default, set):
            # make a py27 and py35 compatible representation. See bug 1771804
            default = 'set([%s])' % ','.join(sorted([six.text_type(v)
                                                     for v in self._default]))
        else:
            default = str(self._default)
        return '%s(default=%s,nullable=%s)' % (self._type.__class__.__name__,
                                               default, self._nullable)

    @property
    def nullable(self):
        return self._nullable

    @property
    def default(self):
        return self._default

    @property
    def read_only(self):
        return self._read_only

    def _null(self, obj, attr):
        if self.nullable:
            return None
        elif self._default != UnspecifiedDefault:
            # NOTE(danms): We coerce the default value each time the field
            # is set to None as our contract states that we'll let the type
            # examine the object and attribute name at that time.
            return self._type.coerce(obj, attr, copy.deepcopy(self._default))
        else:
            raise ValueError(_("Field `%s' cannot be None") % attr)

    def coerce(self, obj, attr, value):
        """Coerce a value to a suitable type.

        This is called any time you set a value on an object, like:

          foo.myint = 1

        and is responsible for making sure that the value (1 here) is of
        the proper type, or can be sanely converted.

        This also handles the potentially nullable or defaultable
        nature of the field and calls the coerce() method on a
        FieldType to actually do the coercion.

        :param:obj: The object being acted upon
        :param:attr: The name of the attribute/field being set
        :param:value: The value being set
        :returns: The properly-typed value
        """
        if value is None:
            return self._null(obj, attr)
        else:
            return self._type.coerce(obj, attr, value)

    def from_primitive(self, obj, attr, value):
        """Deserialize a value from primitive form.

        This is responsible for deserializing a value from primitive
        into regular form. It calls the from_primitive() method on a
        FieldType to do the actual deserialization.

        :param:obj: The object being acted upon
        :param:attr: The name of the attribute/field being deserialized
        :param:value: The value to be deserialized
        :returns: The deserialized value
        """
        if value is None:
            return None
        else:
            return self._type.from_primitive(obj, attr, value)

    def to_primitive(self, obj, attr, value):
        """Serialize a value to primitive form.

        This is responsible for serializing a value to primitive
        form. It calls to_primitive() on a FieldType to do the actual
        serialization.

        :param:obj: The object being acted upon
        :param:attr: The name of the attribute/field being serialized
        :param:value: The value to be serialized
        :returns: The serialized value
        """
        if value is None:
            return None
        else:
            return self._type.to_primitive(obj, attr, value)

    def describe(self):
        """Return a short string describing the type of this field."""
        name = self._type.describe()
        prefix = self.nullable and 'Nullable' or ''
        return prefix + name

    def stringify(self, value):
        if value is None:
            return 'None'
        else:
            return self._type.stringify(value)

    def get_schema(self):
        schema = self._type.get_schema()
        schema.update({'readonly': self.read_only})
        if self.nullable:
            schema['type'].append('null')
        default = self.default
        if default != UnspecifiedDefault:
            schema.update({'default': default})
        return schema


class String(FieldType):
    @staticmethod
    def coerce(obj, attr, value):
        # FIXME(danms): We should really try to avoid the need to do this
        accepted_types = six.integer_types + (float, six.string_types,
                                              datetime.datetime)
        if isinstance(value, accepted_types):
            return six.text_type(value)
        else:
            raise ValueError(_('A string is required in field %(attr)s, '
                               'not a %(type)s') %
                             {'attr': attr, 'type': type(value).__name__})

    @staticmethod
    def stringify(value):
        return '\'%s\'' % value

    def get_schema(self):
        return {'type': ['string']}


class SensitiveString(String):
    """A string field type that may contain sensitive (password) information.

    Passwords in the string value are masked when stringified.
    """
    def stringify(self, value):
        return super(SensitiveString, self).stringify(
            strutils.mask_password(value))


class VersionPredicate(String):
    @staticmethod
    def coerce(obj, attr, value):
        try:
            versionpredicate.VersionPredicate('check (%s)' % value)
        except ValueError:
            raise ValueError(_('Version %(val)s is not a valid predicate in '
                               'field %(attr)s') %
                             {'val': value, 'attr': attr})
        return value


class Enum(String):
    def __init__(self, valid_values, **kwargs):
        if not valid_values:
            raise exception.EnumRequiresValidValuesError()
        try:
            # Test validity of the values
            for value in valid_values:
                super(Enum, self).coerce(None, 'init', value)
        except (TypeError, ValueError):
            raise exception.EnumValidValuesInvalidError()
        self._valid_values = valid_values
        super(Enum, self).__init__(**kwargs)

    @property
    def valid_values(self):
        return copy.copy(self._valid_values)

    def coerce(self, obj, attr, value):
        if value not in self._valid_values:
            msg = _("Field value %s is invalid") % value
            raise ValueError(msg)
        return super(Enum, self).coerce(obj, attr, value)

    def stringify(self, value):
        if value not in self._valid_values:
            msg = _("Field value %s is invalid") % value
            raise ValueError(msg)
        return super(Enum, self).stringify(value)

    def get_schema(self):
        schema = super(Enum, self).get_schema()
        schema['enum'] = self._valid_values
        return schema


class StringPattern(FieldType):
    def get_schema(self):
        if hasattr(self, "PATTERN"):
            return {'type': ['string'], 'pattern': self.PATTERN}
        else:
            msg = _("%s has no pattern") % self.__class__.__name__
            raise AttributeError(msg)


class UUID(StringPattern):

    PATTERN = (r'^[a-fA-F0-9]{8}-?[a-fA-F0-9]{4}-?[a-fA-F0-9]{4}-?[a-fA-F0-9]'
               r'{4}-?[a-fA-F0-9]{12}$')

    @staticmethod
    def coerce(obj, attr, value):
        # FIXME(danms): We should actually verify the UUIDness here
        with warnings.catch_warnings():
            # Change the warning action only if no other filter exists
            # for this warning to allow the client to define other action
            # like 'error' for this warning.
            warnings.filterwarnings(action="once", append=True)
            try:
                uuid.UUID("%s" % value)
            except Exception:
                # This is to ensure no breaking behaviour for current
                # users
                warnings.warn("%s is an invalid UUID. Using UUIDFields "
                              "with invalid UUIDs is no longer "
                              "supported, and will be removed in a future "
                              "release. Please update your "
                              "code to input valid UUIDs or accept "
                              "ValueErrors for invalid UUIDs. See "
                              "https://docs.openstack.org/oslo.versionedobjects/latest/reference/fields.html#oslo_versionedobjects.fields.UUIDField "  # noqa
                              "for further details" %
                              repr(value).encode('utf8'),
                              FutureWarning)

            return "%s" % value


class MACAddress(StringPattern):

    PATTERN = r'^[0-9a-f]{2}(:[0-9a-f]{2}){5}$'
    _REGEX = re.compile(PATTERN)

    @staticmethod
    def coerce(obj, attr, value):
        if isinstance(value, six.string_types):
            lowered = value.lower().replace('-', ':')
            if MACAddress._REGEX.match(lowered):
                return lowered
        raise ValueError(_("Malformed MAC %s") % (value,))


class PCIAddress(StringPattern):

    PATTERN = r'^[0-9a-f]{4}:[0-9a-f]{2}:[0-1][0-9a-f].[0-7]$'
    _REGEX = re.compile(PATTERN)

    @staticmethod
    def coerce(obj, attr, value):
        if isinstance(value, six.string_types):
            newvalue = value.lower()
            if PCIAddress._REGEX.match(newvalue):
                return newvalue
        raise ValueError(_("Malformed PCI address %s") % (value,))


class Integer(FieldType):
    @staticmethod
    def coerce(obj, attr, value):
        return int(value)

    def get_schema(self):
        return {'type': ['integer']}


class NonNegativeInteger(FieldType):
    @staticmethod
    def coerce(obj, attr, value):
        v = int(value)
        if v < 0:
            raise ValueError(_('Value must be >= 0 for field %s') % attr)
        return v

    def get_schema(self):
        return {'type': ['integer'], 'minimum': 0}


class Float(FieldType):
    def coerce(self, obj, attr, value):
        return float(value)

    def get_schema(self):
        return {'type': ['number']}


class NonNegativeFloat(FieldType):
    @staticmethod
    def coerce(obj, attr, value):
        v = float(value)
        if v < 0:
            raise ValueError(_('Value must be >= 0 for field %s') % attr)
        return v

    def get_schema(self):
        return {'type': ['number'], 'minimum': 0}


class Boolean(FieldType):
    @staticmethod
    def coerce(obj, attr, value):
        return bool(value)

    def get_schema(self):
        return {'type': ['boolean']}


class FlexibleBoolean(Boolean):
    @staticmethod
    def coerce(obj, attr, value):
        return strutils.bool_from_string(value)


class DateTime(FieldType):
    def __init__(self, tzinfo_aware=True, *args, **kwargs):
        self.tzinfo_aware = tzinfo_aware
        super(DateTime, self).__init__(*args, **kwargs)

    def coerce(self, obj, attr, value):
        if isinstance(value, six.string_types):
            # NOTE(danms): Being tolerant of isotime strings here will help us
            # during our objects transition
            value = timeutils.parse_isotime(value)
        elif not isinstance(value, datetime.datetime):
            raise ValueError(_('A datetime.datetime is required '
                               'in field %(attr)s, not a %(type)s') %
                             {'attr': attr, 'type': type(value).__name__})

        if value.utcoffset() is None and self.tzinfo_aware:
            # NOTE(danms): Legacy objects from sqlalchemy are stored in UTC,
            # but are returned without a timezone attached.
            # As a transitional aid, assume a tz-naive object is in UTC.
            value = value.replace(tzinfo=iso8601.UTC)
        elif not self.tzinfo_aware:
            value = value.replace(tzinfo=None)
        return value

    def from_primitive(self, obj, attr, value):
        return self.coerce(obj, attr, timeutils.parse_isotime(value))

    def get_schema(self):
        return {'type': ['string'], 'format': 'date-time'}

    @staticmethod
    def to_primitive(obj, attr, value):
        return _utils.isotime(value)

    @staticmethod
    def stringify(value):
        return _utils.isotime(value)


class IPAddress(StringPattern):
    @staticmethod
    def coerce(obj, attr, value):
        try:
            return netaddr.IPAddress(value)
        except netaddr.AddrFormatError as e:
            raise ValueError(six.text_type(e))

    def from_primitive(self, obj, attr, value):
        return self.coerce(obj, attr, value)

    @staticmethod
    def to_primitive(obj, attr, value):
        return str(value)


class IPV4Address(IPAddress):
    @staticmethod
    def coerce(obj, attr, value):
        result = IPAddress.coerce(obj, attr, value)
        if result.version != 4:
            raise ValueError(_('Network "%(val)s" is not valid '
                               'in field %(attr)s') %
                             {'val': value, 'attr': attr})
        return result

    def get_schema(self):
        return {'type': ['string'], 'format': 'ipv4'}


class IPV6Address(IPAddress):
    @staticmethod
    def coerce(obj, attr, value):
        result = IPAddress.coerce(obj, attr, value)
        if result.version != 6:
            raise ValueError(_('Network "%(val)s" is not valid '
                               'in field %(attr)s') %
                             {'val': value, 'attr': attr})
        return result

    def get_schema(self):
        return {'type': ['string'], 'format': 'ipv6'}


class IPV4AndV6Address(IPAddress):
    @staticmethod
    def coerce(obj, attr, value):
        result = IPAddress.coerce(obj, attr, value)
        if result.version != 4 and result.version != 6:
            raise ValueError(_('Network "%(val)s" is not valid '
                               'in field %(attr)s') %
                             {'val': value, 'attr': attr})
        return result

    def get_schema(self):
        return {'oneOf': [IPV4Address().get_schema(),
                          IPV6Address().get_schema()]}


class IPNetwork(IPAddress):
    @staticmethod
    def coerce(obj, attr, value):
        try:
            return netaddr.IPNetwork(value)
        except netaddr.AddrFormatError as e:
            raise ValueError(six.text_type(e))


class IPV4Network(IPNetwork):

    PATTERN = (r'^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-'
               r'9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])(\/([0-9]|[1-2]['
               r'0-9]|3[0-2]))$')

    @staticmethod
    def coerce(obj, attr, value):
        try:
            return netaddr.IPNetwork(value, version=4)
        except netaddr.AddrFormatError as e:
            raise ValueError(six.text_type(e))


class IPV6Network(IPNetwork):

    def __init__(self, *args, **kwargs):
        super(IPV6Network, self).__init__(*args, **kwargs)
        self.PATTERN = self._create_pattern()

    @staticmethod
    def coerce(obj, attr, value):
        try:
            return netaddr.IPNetwork(value, version=6)
        except netaddr.AddrFormatError as e:
            raise ValueError(six.text_type(e))

    def _create_pattern(self):
        ipv6seg = '[0-9a-fA-F]{1,4}'
        ipv4seg = '(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])'

        return (
            # Pattern based on answer to
            # http://stackoverflow.com/questions/53497/regular-expression-that-matches-valid-ipv6-addresses
            '^'
            # 1:2:3:4:5:6:7:8
            '(' + ipv6seg + ':){7,7}' + ipv6seg + '|'
            # 1:: 1:2:3:4:5:6:7::
            '(' + ipv6seg + ':){1,7}:|'
            # 1::8 1:2:3:4:5:6::8 1:2:3:4:5:6::8
            '(' + ipv6seg + ':){1,6}:' + ipv6seg + '|'
            # 1::7:8 1:2:3:4:5::7:8 1:2:3:4:5::8
            '(' + ipv6seg + ':){1,5}(:' + ipv6seg + '){1,2}|'
            # 1::6:7:8 1:2:3:4::6:7:8 1:2:3:4::8
            '(' + ipv6seg + ':){1,4}(:' + ipv6seg + '){1,3}|'
            # 1::5:6:7:8 1:2:3::5:6:7:8 1:2:3::8
            '(' + ipv6seg + ':){1,3}(:' + ipv6seg + '){1,4}|'
            # 1::4:5:6:7:8 1:2::4:5:6:7:8 1:2::8
            '(' + ipv6seg + ':){1,2}(:' + ipv6seg + '){1,5}|' +
            # 1::3:4:5:6:7:8 1::3:4:5:6:7:8 1::8
            ipv6seg + ':((:' + ipv6seg + '){1,6})|'
            # ::2:3:4:5:6:7:8 ::2:3:4:5:6:7:8 ::8 ::
            ':((:' + ipv6seg + '){1,7}|:)|'
            # fe80::7:8%eth0 fe80::7:8%1
            'fe80:(:[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|'
            # ::255.255.255.255 ::ffff:255.255.255.255 ::ffff:0:255.255.255.255
            '::(ffff(:0{1,4}){0,1}:){0,1}'
            '(' + ipv4seg + r'\.){3,3}' +
            ipv4seg + '|'
            # 2001:db8:3:4::192.0.2.33 64:ff9b::192.0.2.33
            '(' + ipv6seg + ':){1,4}:'
            '(' + ipv4seg + r'\.){3,3}' +
            ipv4seg +
            # /128
            r'(\/(d|dd|1[0-1]d|12[0-8]))$'
            )


class CompoundFieldType(FieldType):
    def __init__(self, element_type, **field_args):
        self._element_type = Field(element_type, **field_args)


class List(CompoundFieldType):
    def coerce(self, obj, attr, value):

        if (not isinstance(value, Iterable) or
           isinstance(value, six.string_types + (Mapping,))):
            raise ValueError(_('A list is required in field %(attr)s, '
                               'not a %(type)s') %
                             {'attr': attr, 'type': type(value).__name__})
        coerced_list = CoercedList()
        coerced_list.enable_coercing(self._element_type, obj, attr)
        coerced_list.extend(value)
        return coerced_list

    def to_primitive(self, obj, attr, value):
        return [self._element_type.to_primitive(obj, attr, x) for x in value]

    def from_primitive(self, obj, attr, value):
        return [self._element_type.from_primitive(obj, attr, x) for x in value]

    def stringify(self, value):
        return '[%s]' % (
            ','.join([self._element_type.stringify(x) for x in value]))

    def get_schema(self):
        return {'type': ['array'], 'items': self._element_type.get_schema()}


class Dict(CompoundFieldType):
    def coerce(self, obj, attr, value):
        if not isinstance(value, dict):
            raise ValueError(_('A dict is required in field %(attr)s, '
                               'not a %(type)s') %
                             {'attr': attr, 'type': type(value).__name__})
        coerced_dict = CoercedDict()
        coerced_dict.enable_coercing(self._element_type, obj, attr)
        coerced_dict.update(value)
        return coerced_dict

    def to_primitive(self, obj, attr, value):
        primitive = {}
        for key, element in value.items():
            primitive[key] = self._element_type.to_primitive(
                obj, '%s["%s"]' % (attr, key), element)
        return primitive

    def from_primitive(self, obj, attr, value):
        concrete = {}
        for key, element in value.items():
            concrete[key] = self._element_type.from_primitive(
                obj, '%s["%s"]' % (attr, key), element)
        return concrete

    def stringify(self, value):
        return '{%s}' % (
            ','.join(['%s=%s' % (key, self._element_type.stringify(val))
                      for key, val in sorted(value.items())]))

    def get_schema(self):
        return {'type': ['object'],
                'additionalProperties': self._element_type.get_schema()}


class DictProxyField(object):
    """Descriptor allowing us to assign pinning data as a dict of key_types

    This allows us to have an object field that will be a dict of key_type
    keys, allowing that will convert back to string-keyed dict.

    This will take care of the conversion while the dict field will make sure
    that we store the raw json-serializable data on the object.

    key_type should return a type that unambiguously responds to six.text_type
    so that calling key_type on it yields the same thing.
    """
    def __init__(self, dict_field_name, key_type=int):
        self._fld_name = dict_field_name
        self._key_type = key_type

    def __get__(self, obj, obj_type):
        if obj is None:
            return self
        if getattr(obj, self._fld_name) is None:
            return
        return {self._key_type(k): v
                for k, v in getattr(obj, self._fld_name).items()}

    def __set__(self, obj, val):
        if val is None:
            setattr(obj, self._fld_name, val)
        else:
            setattr(obj, self._fld_name,
                    {six.text_type(k): v for k, v in val.items()})


class Set(CompoundFieldType):
    def coerce(self, obj, attr, value):
        if not isinstance(value, set):
            raise ValueError(_('A set is required in field %(attr)s, '
                               'not a %(type)s') %
                             {'attr': attr, 'type': type(value).__name__})
        coerced_set = CoercedSet()
        coerced_set.enable_coercing(self._element_type, obj, attr)
        coerced_set.update(value)
        return coerced_set

    def to_primitive(self, obj, attr, value):
        return tuple(
            self._element_type.to_primitive(obj, attr, x) for x in value)

    def from_primitive(self, obj, attr, value):
        return set([self._element_type.from_primitive(obj, attr, x)
                    for x in value])

    def stringify(self, value):
        return 'set([%s])' % (
            ','.join([self._element_type.stringify(x) for x in value]))

    def get_schema(self):
        return {'type': ['array'], 'uniqueItems': True,
                'items': self._element_type.get_schema()}


class Object(FieldType):
    def __init__(self, obj_name, subclasses=False, **kwargs):
        self._obj_name = obj_name
        self._subclasses = subclasses
        super(Object, self).__init__(**kwargs)

    @staticmethod
    def _get_all_obj_names(obj):
        obj_names = []
        for parent in obj.__class__.mro():
            # Skip mix-ins which are not versioned object subclasses
            if not hasattr(parent, "obj_name"):
                continue
            obj_names.append(parent.obj_name())
        return obj_names

    def coerce(self, obj, attr, value):
        try:
            obj_name = value.obj_name()
        except AttributeError:
            obj_name = ""

        if self._subclasses:
            obj_names = self._get_all_obj_names(value)
        else:
            obj_names = [obj_name]

        if self._obj_name not in obj_names:
            if not obj_name:
                # If we're not dealing with an object, it's probably a
                # primitive so get it's type for the message below.
                obj_name = type(value).__name__
            obj_mod = ''
            if hasattr(obj, '__module__'):
                obj_mod = ''.join([obj.__module__, '.'])
            val_mod = ''
            if hasattr(value, '__module__'):
                val_mod = ''.join([value.__module__, '.'])
            raise ValueError(_('An object of type %(type)s is required '
                               'in field %(attr)s, not a %(valtype)s') %
                             {'type': ''.join([obj_mod, self._obj_name]),
                              'attr': attr, 'valtype': ''.join([val_mod,
                                                                obj_name])})
        return value

    @staticmethod
    def to_primitive(obj, attr, value):
        return value.obj_to_primitive()

    @staticmethod
    def from_primitive(obj, attr, value):
        # FIXME(danms): Avoid circular import from base.py
        from oslo_versionedobjects import base as obj_base
        # NOTE (ndipanov): If they already got hydrated by the serializer, just
        # pass them back unchanged
        if isinstance(value, obj_base.VersionedObject):
            return value
        return obj.obj_from_primitive(value, obj._context)

    def describe(self):
        return "Object<%s>" % self._obj_name

    def stringify(self, value):
        if 'uuid' in value.fields:
            ident = '(%s)' % (value.obj_attr_is_set('uuid') and value.uuid or
                              'UNKNOWN')
        elif 'id' in value.fields:
            ident = '(%s)' % (value.obj_attr_is_set('id') and value.id or
                              'UNKNOWN')
        else:
            ident = ''

        return '%s%s' % (value.obj_name(), ident)

    def get_schema(self):
        from oslo_versionedobjects import base as obj_base
        obj_classes = obj_base.VersionedObjectRegistry.obj_classes()
        if self._obj_name in obj_classes:
            cls = obj_classes[self._obj_name][0]
            namespace_key = cls._obj_primitive_key('namespace')
            name_key = cls._obj_primitive_key('name')
            version_key = cls._obj_primitive_key('version')
            data_key = cls._obj_primitive_key('data')
            changes_key = cls._obj_primitive_key('changes')
            field_schemas = {key: field.get_schema()
                             for key, field in cls.fields.items()}
            required_fields = [key for key, field in sorted(cls.fields.items())
                               if not field.nullable]
            schema = {
                'type': ['object'],
                'properties': {
                    namespace_key: {
                        'type': 'string'
                    },
                    name_key: {
                        'type': 'string'
                    },
                    version_key: {
                        'type': 'string'
                    },
                    changes_key: {
                        'type': 'array',
                        'items': {
                            'type': 'string'
                        }
                    },
                    data_key: {
                        'type': 'object',
                        'description': 'fields of %s' % self._obj_name,
                        'properties': field_schemas,
                    },
                },
                'required': [namespace_key, name_key, version_key, data_key]
            }

            if required_fields:
                schema['properties'][data_key]['required'] = required_fields

            return schema
        else:
            raise exception.UnsupportedObjectError(objtype=self._obj_name)


class AutoTypedField(Field):
    AUTO_TYPE = None

    def __init__(self, **kwargs):
        super(AutoTypedField, self).__init__(self.AUTO_TYPE, **kwargs)


class StringField(AutoTypedField):
    AUTO_TYPE = String()


class SensitiveStringField(AutoTypedField):
    """Field type that masks passwords when the field is stringified."""
    AUTO_TYPE = SensitiveString()


class VersionPredicateField(AutoTypedField):
    AUTO_TYPE = VersionPredicate()


class BaseEnumField(AutoTypedField):
    '''Base class for all enum field types

    This class should not be directly instantiated. Instead
    subclass it and set AUTO_TYPE to be a SomeEnum()
    where SomeEnum is a subclass of Enum.
    '''

    def __init__(self, **kwargs):
        if self.AUTO_TYPE is None:
            raise exception.EnumFieldUnset(
                fieldname=self.__class__.__name__)

        if not isinstance(self.AUTO_TYPE, Enum):
            raise exception.EnumFieldInvalid(
                typename=self.AUTO_TYPE.__class__.__name__,
                fieldname=self.__class__.__name__)

        super(BaseEnumField, self).__init__(**kwargs)

    def __repr__(self):
        valid_values = self._type.valid_values
        args = {
            'nullable': self._nullable,
            'default': self._default,
            }
        args.update({'valid_values': valid_values})
        return '%s(%s)' % (self._type.__class__.__name__,
                           ','.join(['%s=%s' % (k, v)
                                     for k, v in sorted(args.items())]))

    @property
    def valid_values(self):
        """Return the list of valid values for the field."""
        return self._type.valid_values


class EnumField(BaseEnumField):
    '''Anonymous enum field type

    This class allows for anonymous enum types to be
    declared, simply by passing in a list of valid values
    to its constructor. It is generally preferable though,
    to create an explicit named enum type by sub-classing
    the BaseEnumField type directly.
    '''

    def __init__(self, valid_values, **kwargs):
        self.AUTO_TYPE = Enum(valid_values=valid_values)
        super(EnumField, self).__init__(**kwargs)


class StateMachine(EnumField):
    """A mixin that can be applied to an EnumField to enforce a state machine

    e.g: Setting the code below on a field will ensure an object cannot
    transition from ERROR to ACTIVE

    :example:
        .. code-block:: python

            class FakeStateMachineField(fields.EnumField, fields.StateMachine):

                ACTIVE = 'ACTIVE'
                PENDING = 'PENDING'
                ERROR = 'ERROR'
                DELETED = 'DELETED'

                ALLOWED_TRANSITIONS = {
                    ACTIVE: {
                        PENDING,
                        ERROR,
                        DELETED,
                    },
                    PENDING: {
                        ACTIVE,
                        ERROR
                    },
                    ERROR: {
                        PENDING,
                    },
                    DELETED: {}  # This is a terminal state
                }

                _TYPES = (ACTIVE, PENDING, ERROR, DELETED)

                def __init__(self, **kwargs):
                    super(FakeStateMachineField, self).__init__(
                    self._TYPES, **kwargs)

    """
    # This is dict of states, that have dicts of states an object is
    # allowed to transition to

    ALLOWED_TRANSITIONS = {}

    def _my_name(self, obj):
        for name, field in obj.fields.items():
            if field == self:
                return name
        return 'unknown'

    def coerce(self, obj, attr, value):
        super(StateMachine, self).coerce(obj, attr, value)
        my_name = self._my_name(obj)
        msg = _("%(object)s.%(name)s is not allowed to transition out of "
                "%(value)s state")

        if attr in obj:
            current_value = getattr(obj, attr)
        else:
            return value

        if current_value in self.ALLOWED_TRANSITIONS:

            if value in self.ALLOWED_TRANSITIONS[current_value]:
                return value
            else:
                msg = _(
                    "%(object)s.%(name)s is not allowed to transition out of "
                    "'%(current_value)s' state to '%(value)s' state, choose "
                    "from %(options)r")
        msg = msg % {
            'object': obj.obj_name(),
            'name': my_name,
            'current_value': current_value,
            'value': value,
            'options': [x for x in self.ALLOWED_TRANSITIONS[current_value]]
        }
        raise ValueError(msg)


class UUIDField(AutoTypedField):
    """UUID Field Type

    .. warning::

        This class does not actually validate UUIDs. This will happen in a
        future major version of oslo.versionedobjects

    To validate that you have valid UUIDs you need to do the following in
    your own objects/fields.py

    :Example:
        .. code-block:: python

            import oslo_versionedobjects.fields as ovo_fields

            class UUID(ovo_fields.UUID):
                 def coerce(self, obj, attr, value):
                    uuid.UUID(value)
                    return str(value)


            class UUIDField(ovo_fields.AutoTypedField):
                AUTO_TYPE = UUID()

    and then in your objects use
    ``<your_projects>.object.fields.UUIDField``.

    This will become default behaviour in the future.
    """
    AUTO_TYPE = UUID()


class MACAddressField(AutoTypedField):
    AUTO_TYPE = MACAddress()


class PCIAddressField(AutoTypedField):
    AUTO_TYPE = PCIAddress()


class IntegerField(AutoTypedField):
    AUTO_TYPE = Integer()


class NonNegativeIntegerField(AutoTypedField):
    AUTO_TYPE = NonNegativeInteger()


class FloatField(AutoTypedField):
    AUTO_TYPE = Float()


class NonNegativeFloatField(AutoTypedField):
    AUTO_TYPE = NonNegativeFloat()


# This is a strict interpretation of boolean
# values using Python's semantics for truth/falsehood
class BooleanField(AutoTypedField):
    AUTO_TYPE = Boolean()


# This is a flexible interpretation of boolean
# values using common user friendly semantics for
# truth/falsehood. ie strings like 'yes', 'no',
# 'on', 'off', 't', 'f' get mapped to values you
# would expect.
class FlexibleBooleanField(AutoTypedField):
    AUTO_TYPE = FlexibleBoolean()


class DateTimeField(AutoTypedField):
    def __init__(self, tzinfo_aware=True, **kwargs):
        self.AUTO_TYPE = DateTime(tzinfo_aware=tzinfo_aware)
        super(DateTimeField, self).__init__(**kwargs)


class DictOfStringsField(AutoTypedField):
    AUTO_TYPE = Dict(String())


class DictOfNullableStringsField(AutoTypedField):
    AUTO_TYPE = Dict(String(), nullable=True)


class DictOfIntegersField(AutoTypedField):
    AUTO_TYPE = Dict(Integer())


class ListOfStringsField(AutoTypedField):
    AUTO_TYPE = List(String())


class DictOfListOfStringsField(AutoTypedField):
    AUTO_TYPE = Dict(List(String()))


class ListOfEnumField(AutoTypedField):
    def __init__(self, valid_values, **kwargs):
        self.AUTO_TYPE = List(Enum(valid_values))
        super(ListOfEnumField, self).__init__(**kwargs)

    def __repr__(self):
        valid_values = self._type._element_type._type.valid_values
        args = {
            'nullable': self._nullable,
            'default': self._default,
            }
        args.update({'valid_values': valid_values})
        return '%s(%s)' % (self._type.__class__.__name__,
                           ','.join(['%s=%s' % (k, v)
                                     for k, v in sorted(args.items())]))


class SetOfIntegersField(AutoTypedField):
    AUTO_TYPE = Set(Integer())


class ListOfSetsOfIntegersField(AutoTypedField):
    AUTO_TYPE = List(Set(Integer()))


class ListOfIntegersField(AutoTypedField):
    AUTO_TYPE = List(Integer())


class ListOfDictOfNullableStringsField(AutoTypedField):
    AUTO_TYPE = List(Dict(String(), nullable=True))


class ObjectField(AutoTypedField):
    def __init__(self, objtype, subclasses=False, **kwargs):
        self.AUTO_TYPE = Object(objtype, subclasses)
        self.objname = objtype
        super(ObjectField, self).__init__(**kwargs)


class ListOfObjectsField(AutoTypedField):
    def __init__(self, objtype, subclasses=False, **kwargs):
        self.AUTO_TYPE = List(Object(objtype, subclasses))
        self.objname = objtype
        super(ListOfObjectsField, self).__init__(**kwargs)


class ListOfUUIDField(AutoTypedField):
    AUTO_TYPE = List(UUID())


class IPAddressField(AutoTypedField):
    AUTO_TYPE = IPAddress()


class IPV4AddressField(AutoTypedField):
    AUTO_TYPE = IPV4Address()


class IPV6AddressField(AutoTypedField):
    AUTO_TYPE = IPV6Address()


class IPV4AndV6AddressField(AutoTypedField):
    AUTO_TYPE = IPV4AndV6Address()


class IPNetworkField(AutoTypedField):
    AUTO_TYPE = IPNetwork()


class IPV4NetworkField(AutoTypedField):
    AUTO_TYPE = IPV4Network()


class IPV6NetworkField(AutoTypedField):
    AUTO_TYPE = IPV6Network()


class CoercedCollectionMixin(object):
    def __init__(self, *args, **kwargs):
        self._element_type = None
        self._obj = None
        self._field = None
        super(CoercedCollectionMixin, self).__init__(*args, **kwargs)

    def enable_coercing(self, element_type, obj, field):
        self._element_type = element_type
        self._obj = obj
        self._field = field


class CoercedList(CoercedCollectionMixin, list):
    """List which coerces its elements

    List implementation which overrides all element-adding methods and
    coercing the element(s) being added to the required element type
    """
    def _coerce_item(self, index, item):
        if hasattr(self, "_element_type") and self._element_type is not None:
            att_name = "%s[%i]" % (self._field, index)
            return self._element_type.coerce(self._obj, att_name, item)
        else:
            return item

    def __setitem__(self, i, y):
        if type(i) is slice:  # compatibility with py3 and [::] slices
            start = i.start or 0
            step = i.step or 1
            coerced_items = [self._coerce_item(start + index * step, item)
                             for index, item in enumerate(y)]
            super(CoercedList, self).__setitem__(i, coerced_items)
        else:
            super(CoercedList, self).__setitem__(i, self._coerce_item(i, y))

    def append(self, x):
        super(CoercedList, self).append(self._coerce_item(len(self) + 1, x))

    def extend(self, t):
        l = len(self)
        coerced_items = [self._coerce_item(l + index, item)
                         for index, item in enumerate(t)]
        super(CoercedList, self).extend(coerced_items)

    def insert(self, i, x):
        super(CoercedList, self).insert(i, self._coerce_item(i, x))

    def __iadd__(self, y):
        l = len(self)
        coerced_items = [self._coerce_item(l + index, item)
                         for index, item in enumerate(y)]
        return super(CoercedList, self).__iadd__(coerced_items)

    def __setslice__(self, i, j, y):
        coerced_items = [self._coerce_item(i + index, item)
                         for index, item in enumerate(y)]
        return super(CoercedList, self).__setslice__(i, j, coerced_items)


class CoercedDict(CoercedCollectionMixin, dict):
    """Dict which coerces its values

    Dict implementation which overrides all element-adding methods and
    coercing the element(s) being added to the required element type
    """

    def _coerce_dict(self, d):
        res = {}
        for key, element in d.items():
            res[key] = self._coerce_item(key, element)
        return res

    def _coerce_item(self, key, item):
        if not isinstance(key, six.string_types):
            # NOTE(guohliu) In order to keep compatibility with python3
            # we need to use six.string_types rather than basestring here,
            # since six.string_types is a tuple, so we need to pass the
            # real type in.
            raise KeyTypeError(six.string_types[0], key)
        if hasattr(self, "_element_type") and self._element_type is not None:
            att_name = "%s[%s]" % (self._field, key)
            return self._element_type.coerce(self._obj, att_name, item)
        else:
            return item

    def __setitem__(self, key, value):
        super(CoercedDict, self).__setitem__(key,
                                             self._coerce_item(key, value))

    def update(self, other=None, **kwargs):
        if other is not None:
            super(CoercedDict, self).update(self._coerce_dict(other),
                                            **self._coerce_dict(kwargs))
        else:
            super(CoercedDict, self).update(**self._coerce_dict(kwargs))

    def setdefault(self, key, default=None):
        return super(CoercedDict, self).setdefault(key,
                                                   self._coerce_item(key,
                                                                     default))


class CoercedSet(CoercedCollectionMixin, set):
    """Set which coerces its values

    Dict implementation which overrides all element-adding methods and
    coercing the element(s) being added to the required element type
    """
    def _coerce_element(self, element):
        if hasattr(self, "_element_type") and self._element_type is not None:
            return self._element_type.coerce(self._obj,
                                             "%s[%s]" % (self._field, element),
                                             element)
        else:
            return element

    def _coerce_iterable(self, values):
        coerced = set()
        for element in values:
            coerced.add(self._coerce_element(element))
        return coerced

    def add(self, value):
        return super(CoercedSet, self).add(self._coerce_element(value))

    def update(self, values):
        return super(CoercedSet, self).update(self._coerce_iterable(values))

    def symmetric_difference_update(self, values):
        return super(CoercedSet, self).symmetric_difference_update(
            self._coerce_iterable(values))

    def __ior__(self, y):
        return super(CoercedSet, self).__ior__(self._coerce_iterable(y))

    def __ixor__(self, y):
        return super(CoercedSet, self).__ixor__(self._coerce_iterable(y))
