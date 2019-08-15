import unittest
import sphinx
import os.path

import wsme.types
from wsmeext import sphinxext

docpath = os.path.join(
    os.path.dirname(__file__),
    'sphinxexample')


class ASampleType(object):
    somebytes = wsme.types.bytes
    sometext = wsme.types.text
    someint = int


class TestSphinxExt(unittest.TestCase):
    def test_buildhtml(self):
        if not os.path.exists('.test_sphinxext/'):
            os.makedirs('.test_sphinxext/')
        try:
            sphinx.main([
                '',
                '-b', 'html',
                '-d', '.test_sphinxext/doctree',
                docpath,
                '.test_sphinxext/html'
            ])
            assert Exception("Should raise SystemExit 0")
        except SystemExit as e:
            assert e.code == 0


class TestDataTypeName(unittest.TestCase):
    def test_user_type(self):
        self.assertEqual(sphinxext.datatypename(ASampleType),
                         'ASampleType')

    def test_dict_type(self):
        d = wsme.types.DictType(str, str)
        self.assertEqual(sphinxext.datatypename(d), 'dict(str: str)')
        d = wsme.types.DictType(str, ASampleType)
        self.assertEqual(sphinxext.datatypename(d), 'dict(str: ASampleType)')

    def test_array_type(self):
        d = wsme.types.ArrayType(str)
        self.assertEqual(sphinxext.datatypename(d), 'list(str)')
        d = wsme.types.ArrayType(ASampleType)
        self.assertEqual(sphinxext.datatypename(d), 'list(ASampleType)')
