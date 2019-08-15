# encoding=utf8

from wsme.exc import (ClientSideError, InvalidInput, MissingArgument,
                      UnknownArgument)
from six import u


def test_clientside_error():
    e = ClientSideError("Test")

    assert e.faultstring == u("Test")


def test_unicode_clientside_error():
    e = ClientSideError(u("\u30d5\u30a1\u30b7\u30ea"))

    assert e.faultstring == u("\u30d5\u30a1\u30b7\u30ea")


def test_invalidinput():
    e = InvalidInput('field', 'badvalue', "error message")

    assert e.faultstring == u(
        "Invalid input for field/attribute field. Value: 'badvalue'. "
        "error message"
    ), e.faultstring


def test_missingargument():
    e = MissingArgument('argname', "error message")

    assert e.faultstring == \
        u('Missing argument: "argname": error message'), e.faultstring


def test_unknownargument():
    e = UnknownArgument('argname', "error message")

    assert e.faultstring == \
        u('Unknown argument: "argname": error message'), e.faultstring
