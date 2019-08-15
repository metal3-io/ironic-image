# encoding=utf8

import unittest

from wsme import WSRoot
import wsme.protocol
import wsme.rest.protocol
from wsme.root import default_prepare_response_body

from six import b, u
from webob import Request


class TestRoot(unittest.TestCase):
    def test_default_transaction(self):
        import transaction
        root = WSRoot(transaction=True)
        assert root._transaction is transaction

        txn = root.begin()
        txn.abort()

    def test_default_prepare_response_body(self):
        default_prepare_response_body(None, [b('a')]) == b('a')
        default_prepare_response_body(None, [b('a'), b('b')]) == b('a\nb')
        default_prepare_response_body(None, [u('a')]) == u('a')
        default_prepare_response_body(None, [u('a'), u('b')]) == u('a\nb')

    def test_protocol_selection_error(self):
        class P(wsme.protocol.Protocol):
            name = "test"

            def accept(self, r):
                raise Exception('test')

        root = WSRoot()
        root.addprotocol(P())

        from webob import Request
        req = Request.blank('/test?check=a&check=b&name=Bob')
        res = root._handle_request(req)
        assert res.status_int == 500
        assert res.content_type == 'text/plain'
        assert (res.text ==
                'Unexpected error while selecting protocol: test'), req.text

    def test_protocol_selection_accept_mismatch(self):
        """Verify that we get a 406 error on wrong Accept header."""
        class P(wsme.protocol.Protocol):
            name = "test"

            def accept(self, r):
                return False

        root = WSRoot()
        root.addprotocol(wsme.rest.protocol.RestProtocol())
        root.addprotocol(P())

        req = Request.blank('/test?check=a&check=b&name=Bob')
        req.method = 'GET'
        res = root._handle_request(req)
        assert res.status_int == 406
        assert res.content_type == 'text/plain'
        assert res.text.startswith(
            'None of the following protocols can handle this request'
        ), req.text

    def test_protocol_selection_content_type_mismatch(self):
        """Verify that we get a 415 error on wrong Content-Type header."""
        class P(wsme.protocol.Protocol):
            name = "test"

            def accept(self, r):
                return False

        root = WSRoot()
        root.addprotocol(wsme.rest.protocol.RestProtocol())
        root.addprotocol(P())

        req = Request.blank('/test?check=a&check=b&name=Bob')
        req.method = 'POST'
        req.headers['Content-Type'] = "test/unsupported"
        res = root._handle_request(req)
        assert res.status_int == 415
        assert res.content_type == 'text/plain'
        assert res.text.startswith(
            'Unacceptable Content-Type: test/unsupported not in'
        ), req.text

    def test_protocol_selection_get_method(self):
        class P(wsme.protocol.Protocol):
            name = "test"

            def accept(self, r):
                return True

        root = WSRoot()
        root.addprotocol(wsme.rest.protocol.RestProtocol())
        root.addprotocol(P())

        req = Request.blank('/test?check=a&check=b&name=Bob')
        req.method = 'GET'
        req.headers['Accept'] = 'test/fake'
        p = root._select_protocol(req)
        assert p.name == "test"

    def test_protocol_selection_post_method(self):
        class P(wsme.protocol.Protocol):
            name = "test"

            def accept(self, r):
                return True

        root = WSRoot()
        root.addprotocol(wsme.rest.protocol.RestProtocol())
        root.addprotocol(P())

        req = Request.blank('/test?check=a&check=b&name=Bob')
        req.headers['Content-Type'] = 'test/fake'
        req.method = 'POST'
        p = root._select_protocol(req)
        assert p.name == "test"
