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

"""Introducing the aborting state

Revision ID: 18440d0834af
Revises: 882b2d84cb1b
Create Date: 2017-12-11 15:40:13.905554

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import sql

from ironic_inspector import introspection_state as istate

# revision identifiers, used by Alembic.
revision = '18440d0834af'
down_revision = '882b2d84cb1b'
branch_labels = None
depends_on = None


old_state = sa.Enum(*(set(istate.States.all()) - {istate.States.aborting}),
                    name='node_state')
new_state = sa.Enum(*istate.States.all(), name='node_state')
Node = sql.table('nodes', sql.column('state', old_state))


def upgrade():
    with op.batch_alter_table('nodes') as batch_op:
        batch_op.alter_column('state', existing_type=old_state,
                              type_=new_state)
