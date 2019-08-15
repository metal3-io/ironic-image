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

"""The code of the PXE boot filtering interface."""

import abc

import six


@six.add_metaclass(abc.ABCMeta)
class FilterDriver(object):
    """The PXE boot filtering interface."""

    @abc.abstractmethod
    def init_filter(self):
        """Initialize the internal driver state.

        This method should be idempotent and may perform system-wide filter
        state changes. Can be synchronous.

        :returns: nothing.
        """

    @abc.abstractmethod
    def sync(self, ironic):
        """Synchronize the filter with ironic and inspector.

        To be called both periodically and as needed by inspector. The filter
        should tear down its internal state if the sync method raises in order
        to "propagate" filtering exception between periodic and on-demand sync
        call. To this end, a driver should raise from the sync call if its
        internal state isn't properly initialized.

        :param ironic: an ironic client instance.
        :returns: nothing.
        """

    @abc.abstractmethod
    def tear_down_filter(self):
        """Reset the filter.

        This method should be idempotent and may perform system-wide filter
        state changes. Can be synchronous.

        :returns: nothing.
        """

    @abc.abstractmethod
    def get_periodic_sync_task(self):
        """Get periodic sync task for the filter.

        :returns: a periodic task to be run in the background.
        """
