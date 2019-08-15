# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Generic Rest Api tools."""

import flask
from oslo_config import cfg
from oslo_utils import uuidutils
import six

from ironic_inspector.common.i18n import _
from ironic_inspector import utils

CONF = cfg.CONF


def raises_coercion_exceptions(fn):
    """Convert coercion function exceptions to utils.Error.

    :raises: utils.Error when the coercion function raises an
             AssertionError or a ValueError
    """
    @six.wraps(fn)
    def inner(*args, **kwargs):
        try:
            ret = fn(*args, **kwargs)
        except (AssertionError, ValueError) as exc:
            raise utils.Error(_('Bad request: %s') % exc, code=400)
        return ret
    return inner


def request_field(field_name):
    """Decorate a function that coerces the specified field.

    :param field_name: name of the field to fetch
    :returns: a decorator
    """
    def outer(fn):
        @six.wraps(fn)
        def inner(*args, **kwargs):
            default = kwargs.pop('default', None)
            field = flask.request.args.get(field_name, default=default)
            if field == default:
                # field not found or the same as the default, just return
                return default
            return fn(field, *args, **kwargs)
        return inner
    return outer


@request_field('marker')
@raises_coercion_exceptions
def marker_field(value):
    """Fetch the pagination marker field from flask.request.args.

    :returns: an uuid
    """
    assert uuidutils.is_uuid_like(value), _('Marker not UUID-like')
    return value


@request_field('limit')
@raises_coercion_exceptions
def limit_field(value):
    """Fetch the pagination limit field from flask.request.args.

    :returns: the limit
    """
    # limit of zero means the default limit
    value = int(value) or CONF.api_max_limit
    assert value >= 0, _('Limit cannot be negative')
    assert value <= CONF.api_max_limit, _('Limit over %s') % CONF.api_max_limit
    return value
