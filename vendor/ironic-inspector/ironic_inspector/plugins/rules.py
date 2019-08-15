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

"""Standard plugins for rules API."""

import operator
import re

from ironicclient import exceptions as ironic_exc
import netaddr

from ironic_inspector.common.i18n import _
from ironic_inspector.plugins import base
from ironic_inspector import utils


LOG = utils.getProcessingLogger(__name__)


def coerce(value, expected):
    if isinstance(expected, float):
        return float(value)
    elif isinstance(expected, int):
        return int(value)
    else:
        return value


class SimpleCondition(base.RuleConditionPlugin):
    op = None

    def check(self, node_info, field, params, **kwargs):
        value = params['value']
        return self.op(coerce(field, value), value)


class EqCondition(SimpleCondition):
    op = operator.eq


class LtCondition(SimpleCondition):
    op = operator.lt


class GtCondition(SimpleCondition):
    op = operator.gt


class LeCondition(SimpleCondition):
    op = operator.le


class GeCondition(SimpleCondition):
    op = operator.ge


class NeCondition(SimpleCondition):
    op = operator.ne


class EmptyCondition(base.RuleConditionPlugin):
    REQUIRED_PARAMS = set()
    ALLOW_NONE = True

    def check(self, node_info, field, params, **kwargs):
        return field in ('', None, [], {})


class NetCondition(base.RuleConditionPlugin):
    def validate(self, params, **kwargs):
        super(NetCondition, self).validate(params, **kwargs)
        # Make sure it does not raise
        try:
            netaddr.IPNetwork(params['value'])
        except netaddr.AddrFormatError as exc:
            raise ValueError('invalid value: %s' % exc)

    def check(self, node_info, field, params, **kwargs):
        network = netaddr.IPNetwork(params['value'])
        return netaddr.IPAddress(field) in network


class ReCondition(base.RuleConditionPlugin):
    def validate(self, params, **kwargs):
        try:
            re.compile(params['value'])
        except re.error as exc:
            raise ValueError(_('invalid regular expression: %s') % exc)


class MatchesCondition(ReCondition):
    def check(self, node_info, field, params, **kwargs):
        regexp = params['value']
        if regexp[-1] != '$':
            regexp += '$'
        return re.match(regexp, str(field)) is not None


class ContainsCondition(ReCondition):
    def check(self, node_info, field, params, **kwargs):
        return re.search(params['value'], str(field)) is not None


class FailAction(base.RuleActionPlugin):
    REQUIRED_PARAMS = {'message'}

    def apply(self, node_info, params, **kwargs):
        raise utils.Error(params['message'], node_info=node_info)


class SetAttributeAction(base.RuleActionPlugin):
    # NOTE(iurygregory): set as optional to accept None as value, check
    # that the key 'value' is present, otherwise will raise ValueError.
    OPTIONAL_PARAMS = {'value', 'reset_interfaces'}
    REQUIRED_PARAMS = {'path'}
    # TODO(dtantsur): proper validation of path

    FORMATTED_PARAMS = ['value']

    def apply(self, node_info, params, **kwargs):
        kwargs = {}
        if (params['path'].strip('/') == 'driver'
                and ('reset_interfaces' not in params
                     or params['reset_interfaces'])):
            # Using at least Rocky
            kwargs['reset_interfaces'] = True

        try:
            node_info.patch([{'op': 'add', 'path': params['path'],
                              'value': params['value']}], **kwargs)
        except (TypeError, ironic_exc.NotAcceptable):
            # TODO(dtantsur): remove support for old ironicclient and Queens
            if 'reset_interfaces' in params:
                # An explicit request, report an error.
                raise utils.Error(
                    _('Cannot pass reset_interfaces to set-attribute, '
                      'requires API 1.46 and ironicclient >= 2.5.0'))

            LOG.warning('Not passing reset_interfaces to Ironic, since '
                        ' API 1.46 and/or ironicclient >= 2.5.0 are '
                        'not available', node_info=node_info)
            node_info.patch([{'op': 'add', 'path': params['path'],
                              'value': params['value']}])

    def validate(self, params, **kwargs):
        if 'value' in params:
            super(base.RuleActionPlugin, self).validate(params, **kwargs)
        else:
            msg = _('missing required parameter(s): value')
            raise ValueError(msg)


class SetCapabilityAction(base.RuleActionPlugin):
    REQUIRED_PARAMS = {'name'}
    OPTIONAL_PARAMS = {'value'}

    FORMATTED_PARAMS = ['value']

    def apply(self, node_info, params, **kwargs):
        node_info.update_capabilities(
            **{params['name']: params.get('value')})


class ExtendAttributeAction(base.RuleActionPlugin):
    REQUIRED_PARAMS = {'path', 'value'}
    OPTIONAL_PARAMS = {'unique'}
    # TODO(dtantsur): proper validation of path

    FORMATTED_PARAMS = ['value']

    def apply(self, node_info, params, **kwargs):
        def _replace(values):
            value = params['value']
            if not params.get('unique') or value not in values:
                values.append(value)
            return values

        node_info.replace_field(params['path'], _replace, default=[])


class AddTraitAction(base.RuleActionPlugin):
    REQUIRED_PARAMS = {'name'}

    def apply(self, node_info, params, **kwargs):
        node_info.add_trait(params['name'])


class RemoveTraitAction(base.RuleActionPlugin):
    REQUIRED_PARAMS = {'name'}

    def apply(self, node_info, params, **kwargs):
        node_info.remove_trait(params['name'])
