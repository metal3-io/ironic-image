"""REST+Json protocol implementation."""
from __future__ import absolute_import
import datetime
import decimal

import six

from simplegeneric import generic

import wsme.exc
import wsme.types
from wsme.types import Unset
import wsme.utils


try:
    import simplejson as json
except ImportError:
    import json  # noqa


content_type = 'application/json'
accept_content_types = [
    content_type,
    'text/javascript',
    'application/javascript'
]
ENUM_TRUE = ('true', 't', 'yes', 'y', 'on', '1')
ENUM_FALSE = ('false', 'f', 'no', 'n', 'off', '0')


@generic
def tojson(datatype, value):
    """
    A generic converter from python to jsonify-able datatypes.

    If a non-complex user specific type is to be used in the api,
    a specific tojson should be added::

        from wsme.protocol.restjson import tojson

        myspecialtype = object()

        @tojson.when_object(myspecialtype)
        def myspecialtype_tojson(datatype, value):
            return str(value)
    """
    if value is None:
        return None
    if wsme.types.iscomplex(datatype):
        d = dict()
        for attr in wsme.types.list_attributes(datatype):
            attr_value = getattr(value, attr.key)
            if attr_value is not Unset:
                d[attr.name] = tojson(attr.datatype, attr_value)
        return d
    elif wsme.types.isusertype(datatype):
        return tojson(datatype.basetype, datatype.tobasetype(value))
    return value


@tojson.when_object(wsme.types.bytes)
def bytes_tojson(datatype, value):
    if value is None:
        return None
    return value.decode('ascii')


@tojson.when_type(wsme.types.ArrayType)
def array_tojson(datatype, value):
    if value is None:
        return None
    return [tojson(datatype.item_type, item) for item in value]


@tojson.when_type(wsme.types.DictType)
def dict_tojson(datatype, value):
    if value is None:
        return None
    return dict((
        (tojson(datatype.key_type, item[0]),
            tojson(datatype.value_type, item[1]))
        for item in value.items()
    ))


@tojson.when_object(decimal.Decimal)
def decimal_tojson(datatype, value):
    if value is None:
        return None
    return str(value)


@tojson.when_object(datetime.date)
def date_tojson(datatype, value):
    if value is None:
        return None
    return value.isoformat()


@tojson.when_object(datetime.time)
def time_tojson(datatype, value):
    if value is None:
        return None
    return value.isoformat()


@tojson.when_object(datetime.datetime)
def datetime_tojson(datatype, value):
    if value is None:
        return None
    return value.isoformat()


@generic
def fromjson(datatype, value):
    """A generic converter from json base types to python datatype.

    If a non-complex user specific type is to be used in the api,
    a specific fromjson should be added::

        from wsme.protocol.restjson import fromjson

        class MySpecialType(object):
            pass

        @fromjson.when_object(MySpecialType)
        def myspecialtype_fromjson(datatype, value):
            return MySpecialType(value)
    """
    if value is None:
        return None
    if wsme.types.iscomplex(datatype):
        obj = datatype()
        attributes = wsme.types.list_attributes(datatype)

        # Here we check that all the attributes in the value are also defined
        # in our type definition, otherwise we raise an Error.
        v_keys = set(value.keys())
        a_keys = set(adef.name for adef in attributes)
        if not v_keys <= a_keys:
            raise wsme.exc.UnknownAttribute(None, v_keys - a_keys)

        for attrdef in attributes:
            if attrdef.name in value:
                try:
                    val_fromjson = fromjson(attrdef.datatype,
                                            value[attrdef.name])
                except wsme.exc.UnknownAttribute as e:
                    e.add_fieldname(attrdef.name)
                    raise
                if getattr(attrdef, 'readonly', False):
                    raise wsme.exc.InvalidInput(attrdef.name, val_fromjson,
                                                "Cannot set read only field.")
                setattr(obj, attrdef.key, val_fromjson)
            elif attrdef.mandatory:
                raise wsme.exc.InvalidInput(attrdef.name, None,
                                            "Mandatory field missing.")

        return wsme.types.validate_value(datatype, obj)
    elif wsme.types.isusertype(datatype):
        value = datatype.frombasetype(
            fromjson(datatype.basetype, value))
    return value


@fromjson.when_type(wsme.types.ArrayType)
def array_fromjson(datatype, value):
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValueError("Value not a valid list: %s" % value)
    return [fromjson(datatype.item_type, item) for item in value]


@fromjson.when_type(wsme.types.DictType)
def dict_fromjson(datatype, value):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("Value not a valid dict: %s" % value)
    return dict((
        (fromjson(datatype.key_type, item[0]),
            fromjson(datatype.value_type, item[1]))
        for item in value.items()))


@fromjson.when_object(six.binary_type)
def str_fromjson(datatype, value):
    if (isinstance(value, six.string_types) or
            isinstance(value, six.integer_types) or
            isinstance(value, float)):
        return six.text_type(value).encode('utf8')


@fromjson.when_object(wsme.types.text)
def text_fromjson(datatype, value):
    if value is not None and isinstance(value, wsme.types.bytes):
        return wsme.types.text(value)
    return value


@fromjson.when_object(*six.integer_types + (float,))
def numeric_fromjson(datatype, value):
    """Convert string object to built-in types int, long or float."""
    if value is None:
        return None
    return datatype(value)


@fromjson.when_object(bool)
def bool_fromjson(datatype, value):
    """Convert to bool, restricting strings to just unambiguous values."""
    if value is None:
        return None
    if isinstance(value, six.integer_types + (bool,)):
        return bool(value)
    if value in ENUM_TRUE:
        return True
    if value in ENUM_FALSE:
        return False
    raise ValueError("Value not an unambiguous boolean: %s" % value)


@fromjson.when_object(decimal.Decimal)
def decimal_fromjson(datatype, value):
    if value is None:
        return None
    return decimal.Decimal(value)


@fromjson.when_object(datetime.date)
def date_fromjson(datatype, value):
    if value is None:
        return None
    return wsme.utils.parse_isodate(value)


@fromjson.when_object(datetime.time)
def time_fromjson(datatype, value):
    if value is None:
        return None
    return wsme.utils.parse_isotime(value)


@fromjson.when_object(datetime.datetime)
def datetime_fromjson(datatype, value):
    if value is None:
        return None
    return wsme.utils.parse_isodatetime(value)


def parse(s, datatypes, bodyarg, encoding='utf8'):
    jload = json.load
    if not hasattr(s, 'read'):
        if six.PY3 and isinstance(s, six.binary_type):
            s = s.decode(encoding)
        jload = json.loads
    try:
        jdata = jload(s)
    except ValueError:
        raise wsme.exc.ClientSideError("Request is not in valid JSON format")
    if bodyarg:
        argname = list(datatypes.keys())[0]
        try:
            kw = {argname: fromjson(datatypes[argname], jdata)}
        except ValueError as e:
            raise wsme.exc.InvalidInput(argname, jdata, e.args[0])
        except wsme.exc.UnknownAttribute as e:
            # We only know the fieldname at this level, not in the
            # called function. We fill in this information here.
            e.add_fieldname(argname)
            raise
    else:
        kw = {}
        extra_args = []
        if not isinstance(jdata, dict):
            raise wsme.exc.ClientSideError("Request must be a JSON dict")
        for key in jdata:
            if key not in datatypes:
                extra_args.append(key)
            else:
                try:
                    kw[key] = fromjson(datatypes[key], jdata[key])
                except ValueError as e:
                    raise wsme.exc.InvalidInput(key, jdata[key], e.args[0])
                except wsme.exc.UnknownAttribute as e:
                    # We only know the fieldname at this level, not in the
                    # called function. We fill in this information here.
                    e.add_fieldname(key)
                    raise
        if extra_args:
            raise wsme.exc.UnknownArgument(', '.join(extra_args))
    return kw


def encode_result(value, datatype, **options):
    jsondata = tojson(datatype, value)
    if options.get('nest_result', False):
        jsondata = {options.get('nested_result_attrname', 'result'): jsondata}
    return json.dumps(jsondata)


def encode_error(context, errordetail):
    return json.dumps(errordetail)


def encode_sample_value(datatype, value, format=False):
    r = tojson(datatype, value)
    content = json.dumps(r, ensure_ascii=False, indent=4 if format else 0,
                         sort_keys=format)
    return ('javascript', content)


def encode_sample_params(params, format=False):
    kw = {}
    for name, datatype, value in params:
        kw[name] = tojson(datatype, value)
    content = json.dumps(kw, ensure_ascii=False, indent=4 if format else 0,
                         sort_keys=format)
    return ('javascript', content)


def encode_sample_result(datatype, value, format=False):
    r = tojson(datatype, value)
    content = json.dumps(r, ensure_ascii=False, indent=4 if format else 0,
                         sort_keys=format)
    return ('javascript', content)
