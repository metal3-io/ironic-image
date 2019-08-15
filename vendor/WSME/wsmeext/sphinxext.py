import inspect
import re
import sys

import six

from sphinx import addnodes
from sphinx.ext import autodoc
from sphinx.domains.python import PyClasslike, PyClassmember
from sphinx.domains import Domain, ObjType
from sphinx.directives import ObjectDescription
from sphinx.util.docfields import Field
from sphinx.util.nodes import make_refnode

from sphinx.roles import XRefRole
from sphinx.locale import l_, _

from docutils.parsers.rst import Directive
from docutils.parsers.rst import directives

import wsme
import wsme.types
import wsme.rest.json
import wsme.rest.xml

field_re = re.compile(r':(?P<field>\w+)(\s+(?P<name>\w+))?:')


def datatypename(datatype):
    if isinstance(datatype, wsme.types.UserType):
        return datatype.name
    if isinstance(datatype, wsme.types.DictType):
        return 'dict(%s: %s)' % (datatypename(datatype.key_type),
                                 datatypename(datatype.value_type))
    if isinstance(datatype, wsme.types.ArrayType):
        return 'list(%s)' % datatypename(datatype.item_type)
    return datatype.__name__


def make_sample_object(datatype):
    if datatype is wsme.types.bytes:
        return six.b('samplestring')
    if datatype is wsme.types.text:
        return u'sample unicode'
    if datatype is int:
        return 5
    sample_obj = getattr(datatype, 'sample', datatype)()
    return sample_obj


def get_protocols(names):
    names = list(names)
    protocols = []
    if 'rest' in names:
        names.remove('rest')
        protocols.extend('restjson', 'restxml')
    if 'restjson' in names:
        names.remove('restjson')
        protocols.append(('Json', wsme.rest.json))
    if 'restxml' in names:
        names.remove('restxml')
        protocols.append(('XML', wsme.rest.xml))
    for name in names:
        p = wsme.protocol.getprotocol(name)
        protocols.append((p.displayname or p.name, p))
    return protocols


class SampleType(object):
    """A Sample Type"""

    #: A Int
    aint = int

    def __init__(self, aint=None):
        if aint:
            self.aint = aint

    @classmethod
    def sample(cls):
        return cls(10)


class SampleService(wsme.WSRoot):
    @wsme.expose(SampleType)
    @wsme.validate(SampleType, int, str)
    def change_aint(data, aint, dummy='useless'):
        """
        :param aint: The new value

        :return: The data object with its aint field value changed.
        """
        data.aint = aint
        return data


def getroot(env, force=False):
    root = env.temp_data.get('wsme:root')
    if not force and root:
        return root
    rootpath = env.temp_data.get('wsme:rootpath', env.app.config.wsme_root)

    if rootpath is None:
        return None

    modname, classname = rootpath.rsplit('.', 1)
    __import__(modname)
    module = sys.modules[modname]
    root = getattr(module, classname)
    env.temp_data['wsme:root'] = root
    return root


def scan_services(service, path=[]):
    has_functions = False
    for name in dir(service):
        if name.startswith('_'):
            continue
        a = getattr(service, name)
        if inspect.ismethod(a):
            if hasattr(a, '_wsme_definition'):
                has_functions = True
        if inspect.isclass(a):
            continue
        if len(path) > wsme.rest.APIPATH_MAXLEN:
            raise ValueError("Path is too long: " + str(path))
        for value in scan_services(a, path + [name]):
            yield value
    if has_functions:
        yield service, path


def find_service_path(env, service):
    root = getroot(env)
    if service == root:
        return []
    for s, path in scan_services(root):
        if s == service:
            return path
    return None


class TypeDirective(PyClasslike):
    def get_index_text(self, modname, name_cls):
        return _('%s (webservice type)') % name_cls[0]

    def add_target_and_index(self, name_cls, sig, signode):
        ret = super(TypeDirective, self).add_target_and_index(
            name_cls, sig, signode
        )
        name = name_cls[0]
        types = self.env.domaindata['wsme']['types']
        if name in types:
            self.state_machine.reporter.warning(
                'duplicate type description of %s ' % name)
        types[name] = self.env.docname
        return ret


class AttributeDirective(PyClassmember):
    doc_field_types = [
        Field('datatype', label=l_('Type'), has_arg=False,
              names=('type', 'datatype'))
    ]


def check_samples_slot(value):
    """Validate the samples_slot option to the TypeDocumenter.

    Valid positions are 'before-docstring' and
    'after-docstring'. Using the explicit 'none' disables sample
    output. The default is after-docstring.
    """
    if not value:
        return 'after-docstring'
    val = directives.choice(
        value,
        ('none',              # do not include
         'before-docstring',  # show samples then docstring
         'after-docstring',   # show docstring then samples
         ))
    return val


class TypeDocumenter(autodoc.ClassDocumenter):
    objtype = 'type'
    directivetype = 'type'
    domain = 'wsme'

    required_arguments = 1
    default_samples_slot = 'after-docstring'

    option_spec = dict(
        autodoc.ClassDocumenter.option_spec,
        **{'protocols': lambda l: [v.strip() for v in l.split(',')],
           'samples-slot': check_samples_slot,
           })

    @staticmethod
    def can_document_member(member, membername, isattr, parent):
        # we don't want to be automaticaly used
        # TODO check if the member is registered an an exposed type
        return False

    def format_name(self):
        return self.object.__name__

    def format_signature(self):
        return u''

    def add_directive_header(self, sig):
        super(TypeDocumenter, self).add_directive_header(sig)
        # remove the :module: option that was added by ClassDocumenter
        result_len = len(self.directive.result)
        for index, item in zip(reversed(range(result_len)),
                               reversed(self.directive.result)):
            if ':module:' in item:
                self.directive.result.pop(index)

    def import_object(self):
        if super(TypeDocumenter, self).import_object():
            wsme.types.register_type(self.object)
            return True
        else:
            return False

    def add_content(self, more_content, no_docstring=False):
        # Check where to include the samples
        samples_slot = self.options.samples_slot or self.default_samples_slot

        def add_docstring():
            super(TypeDocumenter, self).add_content(
                more_content, no_docstring)

        def add_samples():
            protocols = get_protocols(
                self.options.protocols or self.env.app.config.wsme_protocols
            )
            content = []
            if protocols:
                sample_obj = make_sample_object(self.object)
                content.extend([
                    l_(u'Data samples:'),
                    u'',
                    u'.. cssclass:: toggle',
                    u''
                ])
                for name, protocol in protocols:
                    language, sample = protocol.encode_sample_value(
                        self.object, sample_obj, format=True)
                    content.extend([
                        name,
                        u'    .. code-block:: ' + language,
                        u'',
                    ])
                    content.extend(
                        u' ' * 8 + line
                        for line in six.text_type(sample).split('\n'))
            for line in content:
                self.add_line(line, u'<wsmeext.sphinxext')

            self.add_line(u'', '<wsmeext.sphinxext>')

        if samples_slot == 'after-docstring':
            add_docstring()
            add_samples()
        elif samples_slot == 'before-docstring':
            add_samples()
            add_docstring()
        else:
            add_docstring()


class AttributeDocumenter(autodoc.AttributeDocumenter):
    datatype = None
    domain = 'wsme'

    @staticmethod
    def can_document_member(member, membername, isattr, parent):
        return isinstance(parent, TypeDocumenter)

    def import_object(self):
        success = super(AttributeDocumenter, self).import_object()
        if success:
            self.datatype = self.object.datatype
        return success

    def add_content(self, more_content, no_docstring=False):
        self.add_line(
            u':type: %s' % datatypename(self.datatype),
            '<wsmeext.sphinxext>'
        )
        self.add_line(u'', '<wsmeext.sphinxext>')
        super(AttributeDocumenter, self).add_content(
            more_content, no_docstring)

    def add_directive_header(self, sig):
        super(AttributeDocumenter, self).add_directive_header(sig)


class RootDirective(Directive):
    """
    This directive is to tell what class is the Webservice root
    """
    has_content = False
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = False
    option_spec = {
        'webpath': directives.unchanged
    }

    def run(self):
        env = self.state.document.settings.env
        rootpath = self.arguments[0].strip()
        env.temp_data['wsme:rootpath'] = rootpath
        if 'wsme:root' in env.temp_data:
            del env.temp_data['wsme:root']
        if 'webpath' in self.options:
            env.temp_data['wsme:webpath'] = self.options['webpath']
        return []


class ServiceDirective(ObjectDescription):
    name = 'service'

    optional_arguments = 1

    def handle_signature(self, sig, signode):
        path = sig.split('/')

        namespace = '/'.join(path[:-1])
        if namespace and not namespace.endswith('/'):
            namespace += '/'

        servicename = path[-1]

        if not namespace and not servicename:
            servicename = '/'

        signode += addnodes.desc_annotation('service ', 'service ')

        if namespace:
            signode += addnodes.desc_addname(namespace, namespace)

        signode += addnodes.desc_name(servicename, servicename)

        return sig


class ServiceDocumenter(autodoc.ClassDocumenter):
    domain = 'wsme'
    objtype = 'service'
    directivetype = 'service'

    def add_directive_header(self, sig):
        super(ServiceDocumenter, self).add_directive_header(sig)
        # remove the :module: option that was added by ClassDocumenter
        result_len = len(self.directive.result)
        for index, item in zip(reversed(range(result_len)),
                               reversed(self.directive.result)):
            if ':module:' in item:
                self.directive.result.pop(index)

    def format_signature(self):
        return u''

    def format_name(self):
        path = find_service_path(self.env, self.object)
        if path is None:
            return
        return '/' + '/'.join(path)


class FunctionDirective(PyClassmember):
    name = 'function'
    objtype = 'function'

    def get_signature_prefix(self, sig):
        return 'function '


def document_function(funcdef, docstrings=None, protocols=['restjson']):
    """A helper function to complete a function documentation with return and
    parameter types"""
    # If the function doesn't have a docstring, add an empty list
    # so the default behaviors below work correctly.
    if not docstrings:
        docstrings = [[]]
    found_params = set()

    for si, docstring in enumerate(docstrings):
        for i, line in enumerate(docstring):
            m = field_re.match(line)
            if m and m.group('field') == 'param':
                found_params.add(m.group('name'))

    next_param_pos = (0, 0)

    for arg in funcdef.arguments:
        content = [
            u':type  %s: :wsme:type:`%s`' % (
                arg.name, datatypename(arg.datatype))
        ]
        if arg.name not in found_params:
            content.insert(0, u':param %s: ' % (arg.name))
            pos = next_param_pos
        else:
            for si, docstring in enumerate(docstrings):
                for i, line in enumerate(docstring):
                    m = field_re.match(line)
                    if m and m.group('field') == 'param' \
                            and m.group('name') == arg.name:
                        pos = (si, i + 1)
                        break
        docstring = docstrings[pos[0]]
        docstring[pos[1]:pos[1]] = content
        next_param_pos = (pos[0], pos[1] + len(content))

    if funcdef.return_type:
        content = [
            u':rtype: %s' % datatypename(funcdef.return_type)
        ]
        pos = None
        for si, docstring in enumerate(docstrings):
            for i, line in enumerate(docstring):
                m = field_re.match(line)
                if m and m.group('field') == 'return':
                    pos = (si, i + 1)
                    break
        else:
            pos = next_param_pos
        docstring = docstrings[pos[0]]
        docstring[pos[1]:pos[1]] = content

    codesamples = []

    if protocols:
        params = []
        for arg in funcdef.arguments:
            params.append((
                arg.name,
                arg.datatype,
                make_sample_object(arg.datatype)
            ))
        codesamples.extend([
            u':%s:' % l_(u'Parameters samples'),
            u'    .. cssclass:: toggle',
            u''
        ])
        for name, protocol in protocols:
            language, sample = protocol.encode_sample_params(
                params, format=True)
            codesamples.extend([
                u' ' * 4 + name,
                u'        .. code-block:: ' + language,
                u'',
            ])
            codesamples.extend((
                u' ' * 12 + line
                for line in six.text_type(sample).split('\n')
            ))

        if funcdef.return_type:
            codesamples.extend([
                u':%s:' % l_(u'Return samples'),
                u'    .. cssclass:: toggle',
                u''
            ])
            sample_obj = make_sample_object(funcdef.return_type)
            for name, protocol in protocols:
                language, sample = protocol.encode_sample_result(
                    funcdef.return_type, sample_obj, format=True)
                codesamples.extend([
                    u' ' * 4 + name,
                    u'        .. code-block:: ' + language,
                    u'',
                ])
                codesamples.extend((
                    u' ' * 12 + line
                    for line in six.text_type(sample).split('\n')
                ))

    docstrings[0:0] = [codesamples]
    return docstrings


class FunctionDocumenter(autodoc.MethodDocumenter):
    domain = 'wsme'
    directivetype = 'function'
    objtype = 'function'
    priority = 1

    option_spec = {
        'path': directives.unchanged,
        'method': directives.unchanged
    }

    @staticmethod
    def can_document_member(member, membername, isattr, parent):
        return (isinstance(parent, ServiceDocumenter) and
                wsme.api.iswsmefunction(member))

    def import_object(self):
        ret = super(FunctionDocumenter, self).import_object()
        self.directivetype = 'function'
        self.wsme_fd = wsme.api.FunctionDefinition.get(self.object)
        self.retann = datatypename(self.wsme_fd.return_type)
        return ret

    def format_args(self):
        args = [arg.name for arg in self.wsme_fd.arguments]
        defaults = [
            arg.default
            for arg in self.wsme_fd.arguments if not arg.mandatory
        ]
        return inspect.formatargspec(args, defaults=defaults)

    def get_doc(self, encoding=None):
        """Inject the type and param fields into the docstrings so that the
        user can add its own param fields to document the parameters"""
        docstrings = super(FunctionDocumenter, self).get_doc(encoding)

        protocols = get_protocols(
            self.options.protocols or self.env.app.config.wsme_protocols
        )

        return document_function(
            self.wsme_fd, docstrings, protocols
        )

    def add_content(self, more_content, no_docstring=False):
        super(FunctionDocumenter, self).add_content(more_content, no_docstring)

    def format_name(self):
        return self.wsme_fd.name

    def add_directive_header(self, sig):
        super(FunctionDocumenter, self).add_directive_header(sig)
        # remove the :module: option that was added by ClassDocumenter
        result_len = len(self.directive.result)
        for index, item in zip(reversed(range(result_len)),
                               reversed(self.directive.result)):
            if ':module:' in item:
                self.directive.result.pop(index)


class WSMEDomain(Domain):
    name = 'wsme'
    label = 'WSME'

    object_types = {
        'type': ObjType(l_('type'), 'type', 'obj'),
        'service': ObjType(l_('service'), 'service', 'obj')
    }

    directives = {
        'type': TypeDirective,
        'attribute':  AttributeDirective,
        'service': ServiceDirective,
        'root': RootDirective,
        'function': FunctionDirective,
    }

    roles = {
        'type': XRefRole()
    }

    initial_data = {
        'types': {},  # fullname -> docname
    }

    def clear_doc(self, docname):
        keys = list(self.data['types'].keys())
        for key in keys:
            value = self.data['types'][key]
            if value == docname:
                del self.data['types'][key]

    def resolve_xref(self, env, fromdocname, builder,
                     type, target, node, contnode):
        if target not in self.data['types']:
            return None
        todocname = self.data['types'][target]
        return make_refnode(
            builder, fromdocname, todocname, target, contnode, target)


def setup(app):
    app.add_domain(WSMEDomain)
    app.add_autodocumenter(TypeDocumenter)
    app.add_autodocumenter(AttributeDocumenter)
    app.add_autodocumenter(ServiceDocumenter)
    app.add_autodocumenter(FunctionDocumenter)

    app.add_config_value('wsme_root', None, 'env')
    app.add_config_value('wsme_webpath', '/', 'env')
    app.add_config_value('wsme_protocols', ['restjson', 'restxml'], 'env')
    app.add_javascript('toggle.js')
    app.add_stylesheet('toggle.css')
