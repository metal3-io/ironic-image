import unittest

try:
    import simplejson as json
except ImportError:
    import json

from wsme.tests.protocol import WSTestRoot
import wsme.tests.test_restjson
import wsme.spore


class TestSpore(unittest.TestCase):
    def test_spore(self):
        spore = wsme.spore.getdesc(WSTestRoot())

        print(spore)

        spore = json.loads(spore)

        assert len(spore['methods']) == 51, str(len(spore['methods']))

        m = spore['methods']['argtypes_setbytesarray']
        assert m['path'] == 'argtypes/setbytesarray', m['path']
        assert m['optional_params'] == ['value']
        assert m['method'] == 'POST'

        m = spore['methods']['argtypes_setdecimal']
        assert m['path'] == 'argtypes/setdecimal'
        assert m['required_params'] == ['value']
        assert m['method'] == 'GET'

        m = spore['methods']['crud_create']
        assert m['path'] == 'crud'
        assert m['method'] == 'PUT'
        assert m['optional_params'] == ['data']

        m = spore['methods']['crud_read']
        assert m['path'] == 'crud'
        assert m['method'] == 'GET'
        assert m['required_params'] == ['ref']

        m = spore['methods']['crud_update']
        assert m['path'] == 'crud'
        assert m['method'] == 'POST'
        assert m['optional_params'] == ['data']

        m = spore['methods']['crud_delete']
        assert m['path'] == 'crud'
        assert m['method'] == 'DELETE'
        assert m['optional_params'] == ['ref']
