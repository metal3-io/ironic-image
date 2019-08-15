"""
A SOAP implementation for wsme.
Parts of the code were taken from the tgwebservices soap implmentation.
"""
from __future__ import absolute_import

import pkg_resources
import datetime
import decimal
import base64
import logging

import six

from wsmeext.soap.simplegeneric import generic
from wsmeext.soap.wsdl import WSDLGenerator

try:
    from lxml import etree as ET
    use_lxml = True
except ImportError:
    from xml.etree import cElementTree as ET  # noqa
    use_lxml = False

from wsme.protocol import CallContext, Protocol, expose

import wsme.types
import wsme.runtime

from wsme import exc
from wsme.utils import parse_isodate, parse_isotime, parse_isodatetime

log = logging.getLogger(__name__)

xsd_ns = 'http://www.w3.org/2001/XMLSchema'
xsi_ns = 'http://www.w3.org/2001/XMLSchema-instance'
soapenv_ns = 'http://schemas.xmlsoap.org/soap/envelope/'

if not use_lxml:
    ET.register_namespace('soap', soapenv_ns)

type_qn = '{%s}type' % xsi_ns
nil_qn = '{%s}nil' % xsi_ns

Envelope_qn = '{%s}Envelope' % soapenv_ns
Body_qn = '{%s}Body' % soapenv_ns
Fault_qn = '{%s}Fault' % soapenv_ns
faultcode_qn = '{%s}faultcode' % soapenv_ns
faultstring_qn = '{%s}faultstring' % soapenv_ns
detail_qn = '{%s}detail' % soapenv_ns


type_registry = {
    wsme.types.bytes: 'xs:string',
    wsme.types.text: 'xs:string',
    int: 'xs:int',
    float: "xs:float",
    bool: "xs:boolean",
    datetime.datetime: "xs:dateTime",
    datetime.date: "xs:date",
    datetime.time: "xs:time",
    decimal.Decimal: "xs:decimal",
    wsme.types.binary: "xs:base64Binary",
}

if not six.PY3:
    type_registry[long] = "xs:long"  # noqa

array_registry = {
    wsme.types.text: "String_Array",
    wsme.types.bytes: "String_Array",
    int: "Int_Array",
    float: "Float_Array",
    bool: "Boolean_Array",
}

if not six.PY3:
    array_registry[long] = "Long_Array"  # noqa


def soap_array(datatype, ns):
    if datatype.item_type in array_registry:
        name = array_registry[datatype.item_type]
    else:
        name = soap_type(datatype.item_type, False) + '_Array'
    if ns:
        name = 'types:' + name
    return name


def soap_type(datatype, ns):
    name = None
    if wsme.types.isarray(datatype):
        return soap_array(datatype, ns)
    if wsme.types.isdict(datatype):
        return None
    if datatype in type_registry:
        stype = type_registry[datatype]
        if not ns:
            stype = stype[3:]
        return stype
    if wsme.types.iscomplex(datatype):
        name = datatype.__name__
        if name and ns:
            name = 'types:' + name
        return name
    if wsme.types.isusertype(datatype):
        return soap_type(datatype.basetype, ns)


def soap_fname(path, funcdef):
    return "".join([path[0]] + [i.capitalize() for i in path[1:]])


class SoapEncoder(object):
    def __init__(self, types_ns):
        self.types_ns = types_ns

    def make_soap_element(self, datatype, tag, value, xsitype=None):
        el = ET.Element(tag)
        if value is None:
            el.set(nil_qn, 'true')
        elif xsitype is not None:
            el.set(type_qn, xsitype)
            el.text = value
        elif wsme.types.isusertype(datatype):
            return self.tosoap(datatype.basetype, tag,
                               datatype.tobasetype(value))
        elif wsme.types.iscomplex(datatype):
            el.set(type_qn, 'types:%s' % (datatype.__name__))
            for attrdef in wsme.types.list_attributes(datatype):
                attrvalue = getattr(value, attrdef.key)
                if attrvalue is not wsme.types.Unset:
                    el.append(self.tosoap(
                        attrdef.datatype,
                        '{%s}%s' % (self.types_ns, attrdef.name),
                        attrvalue
                    ))
        else:
            el.set(type_qn, type_registry.get(datatype))
            if not isinstance(value, wsme.types.text):
                value = wsme.types.text(value)
            el.text = value
        return el

    @generic
    def tosoap(self, datatype, tag, value):
        """Converts a value into xml Element objects for inclusion in the SOAP
        response output (after adding the type to the type_registry).

        If a non-complex user specific type is to be used in the api,
        a specific toxml should be added::

            from wsme.protocol.soap import tosoap, make_soap_element, \
                type_registry

            class MySpecialType(object):
                pass

            type_registry[MySpecialType] = 'xs:MySpecialType'

            @tosoap.when_object(MySpecialType)
            def myspecialtype_tosoap(datatype, tag, value):
                return make_soap_element(datatype, tag, str(value))
        """
        return self.make_soap_element(datatype, tag, value)

    @tosoap.when_type(wsme.types.ArrayType)
    def array_tosoap(self, datatype, tag, value):
        el = ET.Element(tag)
        el.set(type_qn, soap_array(datatype, self.types_ns))
        if value is None:
            el.set(nil_qn, 'true')
        elif len(value) == 0:
            el.append(ET.Element('item'))
        else:
            for item in value:
                el.append(self.tosoap(datatype.item_type, 'item', item))
        return el

    @tosoap.when_object(bool)
    def bool_tosoap(self, datatype, tag, value):
        return self.make_soap_element(
            datatype,
            tag,
            'true' if value is True else 'false' if value is False else None
        )

    @tosoap.when_object(wsme.types.bytes)
    def bytes_tosoap(self, datatype, tag, value):
        log.debug('(bytes_tosoap, %s, %s, %s, %s)', datatype,
                  tag, value, type(value))
        if isinstance(value, wsme.types.bytes):
            value = value.decode('ascii')
        return self.make_soap_element(datatype, tag, value)

    @tosoap.when_object(datetime.datetime)
    def datetime_tosoap(self, datatype, tag, value):
        return self.make_soap_element(
            datatype,
            tag,
            value is not None and value.isoformat() or None
        )

    @tosoap.when_object(wsme.types.binary)
    def binary_tosoap(self, datatype, tag, value):
        log.debug("(%s, %s, %s)", datatype, tag, value)
        value = base64.encodestring(value) if value is not None else None
        if six.PY3:
            value = value.decode('ascii')
        return self.make_soap_element(
            datatype.basetype, tag, value, 'xs:base64Binary'
        )

    @tosoap.when_object(None)
    def None_tosoap(self, datatype, tag, value):
        return self.make_soap_element(datatype, tag, None)


@generic
def fromsoap(datatype, el, ns):
    """
    A generic converter from soap elements to python datatype.

    If a non-complex user specific type is to be used in the api,
    a specific fromsoap should be added.
    """
    if el.get(nil_qn) == 'true':
        return None
    if datatype in type_registry:
        value = datatype(el.text)
    elif wsme.types.isusertype(datatype):
        value = datatype.frombasetype(
            fromsoap(datatype.basetype, el, ns))
    else:
        value = datatype()
        for attr in wsme.types.list_attributes(datatype):
            child = el.find('{%s}%s' % (ns['type'], attr.name))
            if child is not None:
                setattr(value, attr.key, fromsoap(attr.datatype, child, ns))
    return value


@fromsoap.when_type(wsme.types.ArrayType)
def array_fromsoap(datatype, el, ns):
    if len(el) == 1:
        if datatype.item_type \
                not in wsme.types.pod_types + wsme.types.dt_types \
                and len(el[0]) == 0:
            return []
    return [fromsoap(datatype.item_type, child, ns) for child in el]


@fromsoap.when_object(wsme.types.bytes)
def bytes_fromsoap(datatype, el, ns):
    if el.get(nil_qn) == 'true':
        return None
    if el.get(type_qn) not in (None, 'xs:string'):
        raise exc.InvalidInput(el.tag, ET.tostring(el))
    return el.text.encode('ascii') if el.text else six.b('')


@fromsoap.when_object(wsme.types.text)
def text_fromsoap(datatype, el, ns):
    if el.get(nil_qn) == 'true':
        return None
    if el.get(type_qn) not in (None, 'xs:string'):
        raise exc.InvalidInput(el.tag, ET.tostring(el))
    return datatype(el.text if el.text else '')


@fromsoap.when_object(bool)
def bool_fromsoap(datatype, el, ns):
    if el.get(nil_qn) == 'true':
        return None
    if el.get(type_qn) not in (None, 'xs:boolean'):
        raise exc.InvalidInput(el.tag, ET.tostring(el))
    return el.text.lower() != 'false'


@fromsoap.when_object(datetime.date)
def date_fromsoap(datatype, el, ns):
    if el.get(nil_qn) == 'true':
        return None
    if el.get(type_qn) not in (None, 'xs:date'):
        raise exc.InvalidInput(el.tag, ET.tostring(el))
    return parse_isodate(el.text)


@fromsoap.when_object(datetime.time)
def time_fromsoap(datatype, el, ns):
    if el.get(nil_qn) == 'true':
        return None
    if el.get(type_qn) not in (None, 'xs:time'):
        raise exc.InvalidInput(el.tag, ET.tostring(el))
    return parse_isotime(el.text)


@fromsoap.when_object(datetime.datetime)
def datetime_fromsoap(datatype, el, ns):
    if el.get(nil_qn) == 'true':
        return None
    if el.get(type_qn) not in (None, 'xs:dateTime'):
        raise exc.InvalidInput(el.tag, ET.tostring(el))
    return parse_isodatetime(el.text)


@fromsoap.when_object(wsme.types.binary)
def binary_fromsoap(datatype, el, ns):
    if el.get(nil_qn) == 'true':
        return None
    if el.get(type_qn) not in (None, 'xs:base64Binary'):
        raise exc.InvalidInput(el.tag, ET.tostring(el))
    return base64.decodestring(el.text.encode('ascii'))


class SoapProtocol(Protocol):
    """
    SOAP protocol.

    .. autoattribute:: name
    .. autoattribute:: content_types
    """
    name = 'soap'
    displayname = 'SOAP'
    content_types = ['application/soap+xml']

    ns = {
        "soap": "http://www.w3.org/2001/12/soap-envelope",
        "soapenv": "http://schemas.xmlsoap.org/soap/envelope/",
        "soapenc": "http://schemas.xmlsoap.org/soap/encoding/",
    }

    def __init__(self, tns=None, typenamespace=None, baseURL=None,
                 servicename='MyApp'):
        self.tns = tns
        self.typenamespace = typenamespace
        self.servicename = servicename
        self.baseURL = baseURL
        self._name_mapping = {}

        self.encoder = SoapEncoder(typenamespace)

    def get_name_mapping(self, service=None):
        if service not in self._name_mapping:
            self._name_mapping[service] = dict(
                (soap_fname(path, f), path)
                for path, f in self.root.getapi()
                if service is None or (path and path[0] == service)
            )
        return self._name_mapping[service]

    def accept(self, req):
        for ct in self.content_types:
            if req.headers['Content-Type'].startswith(ct):
                return True
        if req.headers.get("Soapaction"):
            return True
        return False

    def iter_calls(self, request):
        yield CallContext(request)

    def extract_path(self, context):
        request = context.request
        el = ET.fromstring(request.body)
        body = el.find('{%(soapenv)s}Body' % self.ns)
        # Extract the service name from the tns
        message = list(body)[0]
        fname = message.tag
        if fname.startswith('{%s}' % self.typenamespace):
            fname = fname[len(self.typenamespace) + 2:]
            mapping = self.get_name_mapping()
            if fname not in mapping:
                raise exc.UnknownFunction(fname)
            path = mapping[fname]
            context.soap_message = message
            return path
        return None

    def read_arguments(self, context):
        kw = {}
        if not hasattr(context, 'soap_message'):
            return kw
        msg = context.soap_message
        for param in msg:
            # FIX for python2.6 (only for lxml)
            if use_lxml and isinstance(param, ET._Comment):
                continue
            name = param.tag[len(self.typenamespace) + 2:]
            arg = context.funcdef.get_arg(name)
            value = fromsoap(arg.datatype, param, {
                'type': self.typenamespace,
            })
            kw[name] = value
        wsme.runtime.check_arguments(context.funcdef, (), kw)
        return kw

    def soap_response(self, path, funcdef, result):
        r = ET.Element('{%s}%sResponse' % (
            self.typenamespace, soap_fname(path, funcdef)
        ))
        log.debug('(soap_response, %s, %s)', funcdef.return_type, result)
        r.append(self.encoder.tosoap(
            funcdef.return_type, '{%s}result' % self.typenamespace, result
        ))
        return r

    def encode_result(self, context, result):
        log.debug('(encode_result, %s)', result)
        if use_lxml:
            envelope = ET.Element(
                Envelope_qn,
                nsmap={'xs': xsd_ns, 'types': self.typenamespace}
            )
        else:
            envelope = ET.Element(Envelope_qn, {
                'xmlns:xs': xsd_ns,
                'xmlns:types': self.typenamespace
            })
        body = ET.SubElement(envelope, Body_qn)
        body.append(self.soap_response(context.path, context.funcdef, result))
        s = ET.tostring(envelope)
        return s

    def get_template(self, name):
        return pkg_resources.resource_string(
            __name__, '%s.html' % name)

    def encode_error(self, context, infos):
        envelope = ET.Element(Envelope_qn)
        body = ET.SubElement(envelope, Body_qn)
        fault = ET.SubElement(body, Fault_qn)
        ET.SubElement(fault, faultcode_qn).text = infos['faultcode']
        ET.SubElement(fault, faultstring_qn).text = infos['faultstring']
        if 'debuginfo' in infos:
            ET.SubElement(fault, detail_qn).text = infos['debuginfo']
        s = ET.tostring(envelope)
        return s

    @expose('/api.wsdl', 'text/xml')
    def api_wsdl(self, service=None):
        if service is None:
            servicename = self.servicename
        else:
            servicename = self.servicename + service.capitalize()
        return WSDLGenerator(
            tns=self.tns,
            types_ns=self.typenamespace,
            soapenc=self.ns['soapenc'],
            service_name=servicename,
            complex_types=self.root.__registry__.complex_types,
            funclist=self.root.getapi(),
            arrays=self.root.__registry__.array_types,
            baseURL=self.baseURL,
            soap_array=soap_array,
            soap_type=soap_type,
            soap_fname=soap_fname,
        ).generate(True)

    def encode_sample_value(self, datatype, value, format=False):
        r = self.encoder.make_soap_element(datatype, 'value', value)
        if format:
            xml_indent(r)
        return ('xml', six.text_type(r))


def xml_indent(elem, level=0):
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for e in elem:
            xml_indent(e, level + 1)
        if not e.tail or not e.tail.strip():
            e.tail = i
    if level and (not elem.tail or not elem.tail.strip()):
        elem.tail = i
