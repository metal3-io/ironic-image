import six
import wsme.types

try:
    from lxml import etree as ET
    use_lxml = True
except ImportError:
    from xml.etree import cElementTree as ET  # noqa
    use_lxml = False


def xml_tostring(el, pretty_print=False):
    if use_lxml:
        return ET.tostring(el, pretty_print=pretty_print)
    return ET.tostring(el)


class NS(object):
    def __init__(self, url):
        self.url = url

    def __call__(self, name):
        return self.qn(name)

    def __str__(self):
        return self.url

    def qn(self, name):
        return '{%s}%s' % (self.url, name)


wsdl_ns = NS("http://schemas.xmlsoap.org/wsdl/")
soap_ns = NS("http://schemas.xmlsoap.org/wsdl/soap/")
xs_ns = NS("http://www.w3.org/2001/XMLSchema")
soapenc_ns = NS("http://schemas.xmlsoap.org/soap/encoding/")


class WSDLGenerator(object):
    def __init__(
            self,
            tns,
            types_ns,
            soapenc,
            service_name,
            complex_types,
            funclist,
            arrays,
            baseURL,
            soap_array,
            soap_type,
            soap_fname):

        self.tns = NS(tns)
        self.types_ns = NS(types_ns)
        self.soapenc = soapenc
        self.service_name = service_name
        self.complex_types = complex_types
        self.funclist = funclist
        self.arrays = arrays
        self.baseURL = baseURL or ''
        self.soap_array = soap_array
        self.soap_fname = soap_fname
        self.soap_type = soap_type

    def gen_complex_type(self, cls):
        complexType = ET.Element(xs_ns('complexType'))
        complexType.set('name', cls.__name__)
        sequence = ET.SubElement(complexType, xs_ns('sequence'))
        for attrdef in wsme.types.list_attributes(cls):
            soap_type = self.soap_type(attrdef.datatype, str(self.types_ns))
            if soap_type is None:
                continue
            element = ET.SubElement(sequence, xs_ns('element'))
            element.set('name', attrdef.name)
            element.set('type', soap_type)
            element.set('minOccurs', '1' if attrdef.mandatory else '0')
            element.set('maxOccurs', '1')
        return complexType

    def gen_array(self, array):
        complexType = ET.Element(xs_ns('complexType'))
        complexType.set('name', self.soap_array(array, False))
        ET.SubElement(
            ET.SubElement(complexType, xs_ns('sequence')),
            xs_ns('element'),
            name='item',
            maxOccurs='unbounded',
            nillable='true',
            type=self.soap_type(array.item_type, self.types_ns)
        )
        return complexType

    def gen_function_types(self, path, funcdef):
        args_el = ET.Element(
            xs_ns('element'),
            name=self.soap_fname(path, funcdef)
        )

        sequence = ET.SubElement(
            ET.SubElement(args_el, xs_ns('complexType')),
            xs_ns('sequence')
        )

        for farg in funcdef.arguments:
            t = self.soap_type(farg.datatype, True)
            if t is None:
                continue
            element = ET.SubElement(
                sequence, xs_ns('element'),
                name=farg.name,
                type=self.soap_type(farg.datatype, True)
            )
            if not farg.mandatory:
                element.set('minOccurs', '0')

        response_el = ET.Element(
            xs_ns('element'),
            name=self.soap_fname(path, funcdef) + 'Response'
        )
        element = ET.SubElement(
            ET.SubElement(
                ET.SubElement(
                    response_el,
                    xs_ns('complexType')
                ),
                xs_ns('sequence')
            ),
            xs_ns('element'),
            name='result'
        )
        return_soap_type = self.soap_type(funcdef.return_type, True)
        if return_soap_type is not None:
            element.set('type', return_soap_type)

        return args_el, response_el

    def gen_types(self):
        types = ET.Element(wsdl_ns('types'))
        schema = ET.SubElement(types, xs_ns('schema'))
        schema.set('elementFormDefault', 'qualified')
        schema.set('targetNamespace', str(self.types_ns))
        for cls in self.complex_types:
            schema.append(self.gen_complex_type(cls))
        for array in self.arrays:
            schema.append(self.gen_array(array))
        for path, funcdef in self.funclist:
            schema.extend(self.gen_function_types(path, funcdef))
        return types

    def gen_functions(self):
        messages = []

        binding = ET.Element(
            wsdl_ns('binding'),
            name='%s_Binding' % self.service_name,
            type='tns:%s_PortType' % self.service_name
        )
        ET.SubElement(
            binding,
            soap_ns('binding'),
            style='document',
            transport='http://schemas.xmlsoap.org/soap/http'
        )

        portType = ET.Element(
            wsdl_ns('portType'),
            name='%s_PortType' % self.service_name
        )

        for path, funcdef in self.funclist:
            soap_fname = self.soap_fname(path, funcdef)

            # message
            req_message = ET.Element(
                wsdl_ns('message'),
                name=soap_fname + 'Request',
                xmlns=str(self.types_ns)
            )
            ET.SubElement(
                req_message,
                wsdl_ns('part'),
                name='parameters',
                element='types:%s' % soap_fname
            )
            messages.append(req_message)

            res_message = ET.Element(
                wsdl_ns('message'),
                name=soap_fname + 'Response',
                xmlns=str(self.types_ns)
            )
            ET.SubElement(
                res_message,
                wsdl_ns('part'),
                name='parameters',
                element='types:%sResponse' % soap_fname
            )
            messages.append(res_message)

            # portType/operation
            operation = ET.SubElement(
                portType,
                wsdl_ns('operation'),
                name=soap_fname
            )
            if funcdef.doc:
                ET.SubElement(
                    operation,
                    wsdl_ns('documentation')
                ).text = funcdef.doc
            ET.SubElement(
                operation, wsdl_ns('input'),
                message='tns:%sRequest' % soap_fname
            )
            ET.SubElement(
                operation, wsdl_ns('output'),
                message='tns:%sResponse' % soap_fname
            )

            # binding/operation
            operation = ET.SubElement(
                binding,
                wsdl_ns('operation'),
                name=soap_fname
            )
            ET.SubElement(
                operation,
                soap_ns('operation'),
                soapAction=soap_fname
            )
            ET.SubElement(
                ET.SubElement(
                    operation,
                    wsdl_ns('input')
                ),
                soap_ns('body'),
                use='literal'
            )
            ET.SubElement(
                ET.SubElement(
                    operation,
                    wsdl_ns('output')
                ),
                soap_ns('body'),
                use='literal'
            )

        return messages + [portType, binding]

    def gen_service(self):
        service = ET.Element(wsdl_ns('service'), name=self.service_name)
        ET.SubElement(
            service,
            wsdl_ns('documentation')
        ).text = six.u('WSDL File for %s') % self.service_name
        ET.SubElement(
            ET.SubElement(
                service,
                wsdl_ns('port'),
                binding='tns:%s_Binding' % self.service_name,
                name='%s_PortType' % self.service_name
            ),
            soap_ns('address'),
            location=self.baseURL
        )

        return service

    def gen_definitions(self):
        attrib = {
            'name': self.service_name,
            'targetNamespace': str(self.tns)
        }
        if use_lxml:
            definitions = ET.Element(
                wsdl_ns('definitions'),
                attrib=attrib,
                nsmap={
                    'xs': str(xs_ns),
                    'soap': str(soap_ns),
                    'types': str(self.types_ns),
                    'tns': str(self.tns)
                }
            )
        else:
            definitions = ET.Element(wsdl_ns('definitions'), **attrib)
            definitions.set('xmlns:types', str(self.types_ns))
            definitions.set('xmlns:tns', str(self.tns))

        definitions.set('name', self.service_name)
        definitions.append(self.gen_types())
        definitions.extend(self.gen_functions())
        definitions.append(self.gen_service())
        return definitions

    def generate(self, format=False):
        return xml_tostring(self.gen_definitions(), pretty_print=format)
