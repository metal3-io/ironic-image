import os
from unittest import TestCase
from pecan import set_config
from pecan import testing

__all__ = ['FunctionalTest']


class FunctionalTest(TestCase):
    """
    Used for functional tests where you need to test your
    literal application and its integration with the framework.
    """

    def setUp(self):
        self.app = testing.load_test_app(os.path.join(
            os.path.dirname(__file__),
            'config.py'
        ))

    def tearDown(self):
        set_config({}, overwrite=True)
