#    Copyright (C) 2014 Yahoo! Inc. All Rights Reserved.
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


class AutomatonException(Exception):
    """Base class for *most* exceptions emitted from this library."""


class InvalidState(AutomatonException):
    """Raised when a invalid state transition is attempted while executing."""


class NotInitialized(AutomatonException):
    """Error raised when an action is attempted on a not inited machine."""


class NotFound(AutomatonException):
    """Raised when some entry in some object doesn't exist."""


class Duplicate(AutomatonException):
    """Raised when a duplicate entry is found."""


class FrozenMachine(AutomatonException):
    """Exception raised when a frozen machine is modified."""

    def __init__(self):
        super(FrozenMachine, self).__init__("Frozen machine can't be modified")
