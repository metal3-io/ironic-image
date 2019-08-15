# -*- coding: utf-8 -*-

# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import importlib
import pkgutil
import re
import sys

import pbr.version
import six

THIS_NAME = __name__
THIS_LIB = sys.modules[THIS_NAME]
TEST_DIR = "%s.tests" % THIS_NAME

__version__ = pbr.version.VersionInfo(THIS_NAME).version_string()

# Any user-specified feature/trait is prefixed with the custom namespace
CUSTOM_NAMESPACE = 'CUSTOM_'


def symbolize(mod_name, name):
    """Given a reference to a Python module object and a short string name for
    a trait, registers a symbol in the module that corresponds to the full
    namespaced trait name.
    """
    leaf_mod = sys.modules[mod_name]
    value_base = '_'.join([m.upper() for m in mod_name.split('.')[1:]])
    value = value_base + '_' + name.upper()
    setattr(THIS_LIB, value, value)  # os_traits.HW_CPU_X86_SSE
    setattr(leaf_mod, name, value)  # os_traits.hw.cpu.x86.SSE


def import_submodules(package, recursive=True):
    """Import all submodules of a module, recursively, including subpackages

    :param package: package (name or actual module)
    :type package: str | module
    :rtype: dict[str, types.ModuleType]
    """
    if isinstance(package, str):
        package = importlib.import_module(package)
    for loader, name, is_pkg in pkgutil.walk_packages(
            package.__path__, package.__name__ + '.'):
        if TEST_DIR in name:
            continue
        imported = importlib.import_module(name)
        for prop in getattr(imported, "TRAITS", []):
            symbolize(name, prop)
        if recursive and is_pkg:
            import_submodules(name)


# This is where the names defined in submodules are imported
import_submodules(sys.modules.get(__name__))


def get_traits(prefix=None, suffix=None):
    """Returns the trait strings in the os_traits module, optionally filtered
    by a supplied prefix and suffix.

    :param prefix: Optional string prefix to filter by. e.g. 'HW_'
    :param suffix: Optional string suffix to filter by, e.g. 'SSE'
    """
    prefix = prefix or ""
    suffix = suffix or ""
    return [
        v for k, v in sys.modules[__name__].__dict__.items()
        if isinstance(v, six.string_types) and
        not k.startswith('_') and
        v.startswith(prefix) and
        v.endswith(suffix) and
        # skip module constants
        k not in ('CUSTOM_NAMESPACE', 'THIS_NAME', 'THIS_LIB', 'TEST_DIR')
    ]


def check_traits(traits, prefix=None):
    """Returns a tuple of two trait string sets, the first set contains valid
    traits, and the second contains others.

    :param traits: An iterable contains trait strings.
    :param prefix: Optional string prefix to filter by. e.g. 'HW_'
    """
    trait_set = set(traits)
    valid_trait_set = set(get_traits(prefix))

    valid_traits = trait_set & valid_trait_set

    return (valid_traits, trait_set - valid_traits)


def is_custom(trait):
    """Returns True if the trait string represents a custom trait, or False
    otherwise.

    :param trait: String name of the trait
    """
    return trait.startswith(CUSTOM_NAMESPACE)


def normalize_name(name):
    """Converts an input string to a legal* custom trait name.

    Legal custom trait names are prefixed with CUSTOM_ and contain only the
    characters A-Z, 0-9, and _ (underscore).

    *Does not attempt to handle length restrictions.

    :param name: A string to be converted.
    :return: A legal* custom trait name.
    """
    if name is None:
        return None
    # Replace non-alphanumeric characters with underscores
    norm_name = re.sub('[^0-9A-Za-z]+', '_', name)
    # Bug #1762789: Do .upper after replacing non alphanumerics.
    return CUSTOM_NAMESPACE + norm_name.upper()
