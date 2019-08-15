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

import abc

from oslo_concurrency import lockutils
from oslo_config import cfg
import six

from ironic_inspector import utils

CONF = cfg.CONF
_LOCK_TEMPLATE = 'node-%s'
_SEMAPHORES = lockutils.Semaphores()


@six.add_metaclass(abc.ABCMeta)
class BaseLock(object):

    @abc.abstractmethod
    def acquire(self, blocking=True):
        """Acquire lock."""

    @abc.abstractmethod
    def release(self):
        """Release lock."""

    @abc.abstractmethod
    def is_locked(self):
        """Return lock status"""


class InternalLock(BaseLock):
    """Locking mechanism based on threading.Semaphore."""

    def __init__(self, uuid):
        self._lock = lockutils.internal_lock(_LOCK_TEMPLATE % uuid,
                                             semaphores=_SEMAPHORES)
        self._locked = False

    def acquire(self, blocking=True):
        if not self._locked:
            self._locked = self._lock.acquire(blocking=blocking)
        return self._locked

    def release(self):
        if self._locked:
            self._lock.release()
            self._locked = False

    def is_locked(self):
        return self._locked

    def __enter__(self):
        self._lock.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._lock.release()


class ToozLock(BaseLock):
    """Locking mechanism based on tooz."""

    def __init__(self, coordinator, uuid, prefix='ironic_inspector_'):
        name = (prefix + uuid).encode()
        self._lock = coordinator.get_lock(name)

    def acquire(self, blocking=True):
        if not self._lock.acquired:
            self._lock.acquire(blocking=blocking)
        return self._lock.acquired

    def release(self):
        if self._lock.acquired:
            self._lock.release()

    def is_locked(self):
        return self._lock.acquired

    def __enter__(self):
        self._lock.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._lock.release()


def get_lock(uuid):
    if CONF.standalone:
        return InternalLock(uuid)

    coordinator = utils.get_coordinator()
    return ToozLock(coordinator, uuid)
