# -*- coding: utf-8 -*-

#    Copyright (C) 2015 Yahoo! Inc. All Rights Reserved.
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

"""Executor rejection strategies."""

import futurist


def reject_when_reached(max_backlog):
    """Returns a function that will raise when backlog goes past max size."""

    def _rejector(executor, backlog):
        if backlog >= max_backlog:
            raise futurist.RejectedSubmission("Current backlog %s is not"
                                              " allowed to go"
                                              " beyond %s" % (backlog,
                                                              max_backlog))

    return _rejector
