from wsme import types

try:
    import simplejson as json
except ImportError:
    import json  # noqa


def getdesc(root, host_url=''):
    methods = {}

    for path, funcdef in root.getapi():
        method = funcdef.extra_options.get('method', None)
        name = '_'.join(path)
        if method is not None:
            path = path[:-1]
        else:
            method = 'GET'
            for argdef in funcdef.arguments:
                if types.iscomplex(argdef.datatype) \
                        or types.isarray(argdef.datatype) \
                        or types.isdict(argdef.datatype):
                    method = 'POST'
                    break

        required_params = []
        optional_params = []
        for argdef in funcdef.arguments:
            if method == 'GET' and argdef.mandatory:
                required_params.append(argdef.name)
            else:
                optional_params.append(argdef.name)

        methods[name] = {
            'method': method,
            'path': '/'.join(path)
        }
        if required_params:
            methods[name]['required_params'] = required_params
        if optional_params:
            methods[name]['optional_params'] = optional_params
        if funcdef.doc:
            methods[name]['documentation'] = funcdef.doc

    formats = []
    for p in root.protocols:
        if p.name == 'restxml':
            formats.append('xml')
        if p.name == 'restjson':
            formats.append('json')

    api = {
        'base_url': host_url + root._webpath,
        'version': '0.1',
        'name': getattr(root, 'name', 'name'),
        'authority': '',
        'formats': [
            'json',
            'xml'
        ],
        'methods': methods
    }

    return json.dumps(api, indent=4)
