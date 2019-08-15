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

"""add_introspection_data_table

Revision ID: bf8dec16023c
Revises: 2970d2d44edc
Create Date: 2018-07-19 18:51:38.124614

"""

from alembic import op
from oslo_db.sqlalchemy import types as db_types
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'bf8dec16023c'
down_revision = '2970d2d44edc'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'introspection_data',
        sa.Column('uuid', sa.String(36), sa.ForeignKey('nodes.uuid'),
                  primary_key=True),
        sa.Column('processed', sa.Boolean, default=False, primary_key=True),
        sa.Column('data', db_types.JsonEncodedDict(mysql_as_long=True).impl,
                  nullable=True),
        mysql_ENGINE='InnoDB',
        mysql_DEFAULT_CHARSET='UTF8'
    )
