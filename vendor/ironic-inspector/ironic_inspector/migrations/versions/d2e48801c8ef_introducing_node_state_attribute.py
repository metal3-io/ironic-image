# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""Introducing Node.state attribute

Revision ID: d2e48801c8ef
Revises: e169a4a81d88
Create Date: 2016-07-29 10:10:32.351661

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import sql

from ironic_inspector import introspection_state as istate


# revision identifiers, used by Alembic.
revision = 'd2e48801c8ef'
down_revision = 'e169a4a81d88'
branch_labels = None
depends_on = None

Node = sql.table('nodes',
                 sql.column('error', sa.String),
                 sql.column('state', sa.Enum(*istate.States.all())))


def upgrade():
    state_enum = sa.Enum(*istate.States.all(), name='node_state')
    state_enum.create(op.get_bind())

    op.add_column('nodes', sa.Column('version_id', sa.String(36),
                                     server_default=''))
    op.add_column('nodes', sa.Column('state', state_enum,
                                     nullable=False,
                                     default=istate.States.finished,
                                     server_default=istate.States.finished))
    # correct the state: finished -> error if Node.error is not null
    stmt = Node.update().where(Node.c.error != sql.null()).values(
        {'state': op.inline_literal(istate.States.error)})
    op.execute(stmt)
