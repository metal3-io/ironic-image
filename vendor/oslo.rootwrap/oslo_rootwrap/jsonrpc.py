# Copyright (c) 2014 Mirantis Inc.
# All Rights Reserved.
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

import base64
import errno
import json
from multiprocessing import connection
from multiprocessing import managers
import socket
import struct
import weakref

from oslo_rootwrap import wrapper


class RpcJSONEncoder(json.JSONEncoder):
    def default(self, o):
        # We need to pass bytes unchanged as they are expected in arguments for
        # and are result of Popen.communicate()
        if isinstance(o, bytes):
            return {"__bytes__": base64.b64encode(o).decode('ascii')}
        # Handle two exception types relevant to command execution
        if isinstance(o, wrapper.NoFilterMatched):
            return {"__exception__": "NoFilterMatched"}
        elif isinstance(o, wrapper.FilterMatchNotExecutable):
            return {"__exception__": "FilterMatchNotExecutable",
                    "match": o.match}
        # Other errors will fail to pass JSON encoding and will be visible on
        # client side
        else:
            return super(RpcJSONEncoder, self).default(o)


# Parse whatever RpcJSONEncoder supplied us with
def rpc_object_hook(obj):
    if "__exception__" in obj:
        type_name = obj.pop("__exception__")
        if type_name not in ("NoFilterMatched", "FilterMatchNotExecutable"):
            return obj
        exc_type = getattr(wrapper, type_name)
        return exc_type(**obj)
    elif "__bytes__" in obj:
        return base64.b64decode(obj["__bytes__"].encode('ascii'))
    else:
        return obj


class JsonListener(object):
    def __init__(self, address, backlog=1):
        self.address = address
        self._socket = socket.socket(socket.AF_UNIX)
        try:
            self._socket.setblocking(True)
            self._socket.bind(address)
            self._socket.listen(backlog)
        except socket.error:
            self._socket.close()
            raise
        self.closed = False
        self._accepted = weakref.WeakSet()

    def accept(self):
        while True:
            try:
                s, _ = self._socket.accept()
            except socket.error as e:
                if e.errno in (errno.EINVAL, errno.EBADF):
                    raise EOFError
                elif e.errno != errno.EINTR:
                    raise
            else:
                break
        s.setblocking(True)
        conn = JsonConnection(s)
        self._accepted.add(conn)
        return conn

    def close(self):
        if not self.closed:
            self._socket.shutdown(socket.SHUT_RDWR)
            self._socket.close()
            self.closed = True

    def get_accepted(self):
        return self._accepted

if hasattr(managers.Server, 'accepter'):
    # In Python 3 accepter() thread has infinite loop. We break it with
    # EOFError, so we should silence this error here.
    def silent_accepter(self):
        try:
            old_accepter(self)
        except EOFError:
            pass
    old_accepter = managers.Server.accepter
    managers.Server.accepter = silent_accepter


class JsonConnection(object):
    def __init__(self, sock):
        sock.setblocking(True)
        self._socket = sock

    def send_bytes(self, s):
        self._socket.sendall(struct.pack('!Q', len(s)))
        self._socket.sendall(s)

    def recv_bytes(self, maxsize=None):
        l = struct.unpack('!Q', self.recvall(8))[0]
        if maxsize is not None and l > maxsize:
            raise RuntimeError("Too big message received")
        s = self.recvall(l)
        return s

    def send(self, obj):
        s = self.dumps(obj)
        self.send_bytes(s)

    def recv(self):
        s = self.recv_bytes()
        return self.loads(s)

    def close(self):
        self._socket.close()

    def half_close(self):
        self._socket.shutdown(socket.SHUT_RD)

    # We have to use slow version of recvall with eventlet because of a bug in
    # GreenSocket.recv_into:
    # https://bitbucket.org/eventlet/eventlet/pull-request/41
    def _recvall_slow(self, size):
        remaining = size
        res = []
        while remaining:
            piece = self._socket.recv(remaining)
            if not piece:
                raise EOFError
            res.append(piece)
            remaining -= len(piece)
        return b''.join(res)

    def recvall(self, size):
        buf = bytearray(size)
        mem = memoryview(buf)
        got = 0
        while got < size:
            piece_size = self._socket.recv_into(mem[got:])
            if not piece_size:
                raise EOFError
            got += piece_size
        # bytearray is mostly compatible with bytes and we could avoid copying
        # data here, but hmac doesn't like it in Python 3.3 (not in 2.7 or 3.4)
        return bytes(buf)

    @staticmethod
    def dumps(obj):
        return json.dumps(obj, cls=RpcJSONEncoder).encode('utf-8')

    @staticmethod
    def loads(s):
        res = json.loads(s.decode('utf-8'), object_hook=rpc_object_hook)
        try:
            kind = res[0]
        except (IndexError, TypeError):
            pass
        else:
            # In Python 2 json returns unicode while multiprocessing needs str
            if (kind in ("#TRACEBACK", "#UNSERIALIZABLE") and
                    not isinstance(res[1], str)):
                res[1] = res[1].encode('utf-8', 'replace')
        return res


class JsonClient(JsonConnection):
    def __init__(self, address, authkey=None):
        sock = socket.socket(socket.AF_UNIX)
        sock.setblocking(True)
        sock.connect(address)
        super(JsonClient, self).__init__(sock)
        if authkey is not None:
            connection.answer_challenge(self, authkey)
            connection.deliver_challenge(self, authkey)
