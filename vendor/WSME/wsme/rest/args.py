import cgi
import datetime
import re

from simplegeneric import generic

from wsme.exc import ClientSideError, UnknownArgument, InvalidInput

from wsme.types import iscomplex, list_attributes, Unset
from wsme.types import UserType, ArrayType, DictType, File
from wsme.utils import parse_isodate, parse_isotime, parse_isodatetime
import wsme.runtime

from six import moves

ARRAY_MAX_SIZE = 1000


@generic
def from_param(datatype, value):
    return datatype(value) if value is not None else None


@from_param.when_object(datetime.date)
def date_from_param(datatype, value):
    return parse_isodate(value) if value else None


@from_param.when_object(datetime.time)
def time_from_param(datatype, value):
    return parse_isotime(value) if value else None


@from_param.when_object(datetime.datetime)
def datetime_from_param(datatype, value):
    return parse_isodatetime(value) if value else None


@from_param.when_object(File)
def filetype_from_param(datatype, value):
    if isinstance(value, cgi.FieldStorage):
        return File(fieldstorage=value)
    return File(content=value)


@from_param.when_type(UserType)
def usertype_from_param(datatype, value):
    return datatype.frombasetype(
        from_param(datatype.basetype, value))


@from_param.when_type(ArrayType)
def array_from_param(datatype, value):
    if value is None:
        return value
    return [
        from_param(datatype.item_type, item)
        for item in value
    ]


@generic
def from_params(datatype, params, path, hit_paths):
    if iscomplex(datatype) and datatype is not File:
        objfound = False
        for key in params:
            if key.startswith(path + '.'):
                objfound = True
                break
        if objfound:
            r = datatype()
            for attrdef in list_attributes(datatype):
                value = from_params(
                    attrdef.datatype,
                    params, '%s.%s' % (path, attrdef.key), hit_paths
                )
                if value is not Unset:
                    setattr(r, attrdef.key, value)
            return r
    else:
        if path in params:
            hit_paths.add(path)
            return from_param(datatype, params[path])
    return Unset


@from_params.when_type(ArrayType)
def array_from_params(datatype, params, path, hit_paths):
    if hasattr(params, 'getall'):
        # webob multidict
        def getall(params, path):
            return params.getall(path)
    elif hasattr(params, 'getlist'):
        # werkzeug multidict
        def getall(params, path):  # noqa
            return params.getlist(path)
    if path in params:
        hit_paths.add(path)
        return [
            from_param(datatype.item_type, value)
            for value in getall(params, path)]

    if iscomplex(datatype.item_type):
        attributes = set()
        r = re.compile('^%s\.(?P<attrname>[^\.])' % re.escape(path))
        for p in params.keys():
            m = r.match(p)
            if m:
                attributes.add(m.group('attrname'))
        if attributes:
            value = []
            for attrdef in list_attributes(datatype.item_type):
                attrpath = '%s.%s' % (path, attrdef.key)
                hit_paths.add(attrpath)
                attrvalues = getall(params, attrpath)
                if len(value) < len(attrvalues):
                    value[-1:] = [
                        datatype.item_type()
                        for i in moves.range(len(attrvalues) - len(value))
                    ]
                for i, attrvalue in enumerate(attrvalues):
                    setattr(
                        value[i],
                        attrdef.key,
                        from_param(attrdef.datatype, attrvalue)
                    )
            return value

    indexes = set()
    r = re.compile('^%s\[(?P<index>\d+)\]' % re.escape(path))

    for p in params.keys():
        m = r.match(p)
        if m:
            indexes.add(int(m.group('index')))

    if not indexes:
        return Unset

    indexes = list(indexes)
    indexes.sort()

    return [from_params(datatype.item_type, params,
                        '%s[%s]' % (path, index), hit_paths)
            for index in indexes]


@from_params.when_type(DictType)
def dict_from_params(datatype, params, path, hit_paths):

    keys = set()
    r = re.compile('^%s\[(?P<key>[a-zA-Z0-9_\.]+)\]' % re.escape(path))

    for p in params.keys():
        m = r.match(p)
        if m:
            keys.add(from_param(datatype.key_type, m.group('key')))

    if not keys:
        return Unset

    return dict((
        (key, from_params(datatype.value_type,
                          params, '%s[%s]' % (path, key), hit_paths))
        for key in keys))


@from_params.when_type(UserType)
def usertype_from_params(datatype, params, path, hit_paths):
    value = from_params(datatype.basetype, params, path, hit_paths)
    if value is not Unset:
        return datatype.frombasetype(value)
    return Unset


def args_from_args(funcdef, args, kwargs):
    newargs = []
    for argdef, arg in zip(funcdef.arguments[:len(args)], args):
        try:
            newargs.append(from_param(argdef.datatype, arg))
        except Exception as e:
            if isinstance(argdef.datatype, UserType):
                datatype_name = argdef.datatype.name
            elif isinstance(argdef.datatype, type):
                datatype_name = argdef.datatype.__name__
            else:
                datatype_name = argdef.datatype.__class__.__name__
            raise InvalidInput(
                argdef.name,
                arg,
                "unable to convert to %(datatype)s. Error: %(error)s" % {
                    'datatype': datatype_name, 'error': e})
    newkwargs = {}
    for argname, value in kwargs.items():
        newkwargs[argname] = from_param(
            funcdef.get_arg(argname).datatype, value
        )
    return newargs, newkwargs


def args_from_params(funcdef, params):
    kw = {}
    hit_paths = set()
    for argdef in funcdef.arguments:
        value = from_params(
            argdef.datatype, params, argdef.name, hit_paths)
        if value is not Unset:
            kw[argdef.name] = value
    paths = set(params.keys())
    unknown_paths = paths - hit_paths
    if '__body__' in unknown_paths:
        unknown_paths.remove('__body__')
    if not funcdef.ignore_extra_args and unknown_paths:
        raise UnknownArgument(', '.join(unknown_paths))
    return [], kw


def args_from_body(funcdef, body, mimetype):
    from wsme.rest import json as restjson
    from wsme.rest import xml as restxml

    if funcdef.body_type is not None:
        datatypes = {funcdef.arguments[-1].name: funcdef.body_type}
    else:
        datatypes = dict(((a.name, a.datatype) for a in funcdef.arguments))

    if not body:
        return (), {}
    if mimetype == "application/x-www-form-urlencoded":
        # the parameters should have been parsed in params
        return (), {}
    elif mimetype in restjson.accept_content_types:
        dataformat = restjson
    elif mimetype in restxml.accept_content_types:
        dataformat = restxml
    else:
        raise ClientSideError("Unknown mimetype: %s" % mimetype,
                              status_code=415)

    try:
        kw = dataformat.parse(
            body, datatypes, bodyarg=funcdef.body_type is not None
        )
    except UnknownArgument:
        if not funcdef.ignore_extra_args:
            raise
        kw = {}

    return (), kw


def combine_args(funcdef, akw, allow_override=False):
    newargs, newkwargs = [], {}
    for args, kwargs in akw:
        for i, arg in enumerate(args):
            n = funcdef.arguments[i].name
            if not allow_override and n in newkwargs:
                raise ClientSideError(
                    "Parameter %s was given several times" % n)
            newkwargs[n] = arg
        for name, value in kwargs.items():
            n = str(name)
            if not allow_override and n in newkwargs:
                raise ClientSideError(
                    "Parameter %s was given several times" % n)
            newkwargs[n] = value
    return newargs, newkwargs


def get_args(funcdef, args, kwargs, params, form, body, mimetype):
    """Combine arguments from :
    * the host framework args and kwargs
    * the request params
    * the request body

    Note that the host framework args and kwargs can be overridden
    by arguments from params of body
    """
    # get the body from params if not given directly
    if not body and '__body__' in params:
        body = params['__body__']

    # extract args from the host args and kwargs
    from_args = args_from_args(funcdef, args, kwargs)

    # extract args from the request parameters
    from_params = args_from_params(funcdef, params)

    # extract args from the form parameters
    if form:
        from_form_params = args_from_params(funcdef, form)
    else:
        from_form_params = (), {}

    # extract args from the request body
    from_body = args_from_body(funcdef, body, mimetype)

    # combine params and body arguments
    from_params_and_body = combine_args(
        funcdef,
        (from_params, from_form_params, from_body)
    )

    args, kwargs = combine_args(
        funcdef,
        (from_args, from_params_and_body),
        allow_override=True
    )
    wsme.runtime.check_arguments(funcdef, args, kwargs)
    return args, kwargs
