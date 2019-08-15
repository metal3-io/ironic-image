import mock
import unittest

from wsme import exc
from wsme.rest import args
from wsme.rest import json


class TestArgs(unittest.TestCase):

    def test_args_from_body(self):

        funcdef = mock.MagicMock()
        body = mock.MagicMock()
        mimetype = "application/json"
        funcdef.ignore_extra_args = True
        json.parse = mock.MagicMock()
        json.parse.side_effect = (exc.UnknownArgument(""))
        resp = args.args_from_body(funcdef, body, mimetype)
        self.assertEqual(resp, ((), {}))
