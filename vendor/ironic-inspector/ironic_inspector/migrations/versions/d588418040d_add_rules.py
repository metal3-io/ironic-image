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

"""Add Rules

Revision ID: d588418040d
Revises: 578f84f38d
Create Date: 2015-09-21 14:31:03.048455

"""

from alembic import op
from oslo_db.sqlalchemy import types
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd588418040d'
down_revision = '578f84f38d'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'rules',
        sa.Column('uuid', sa.String(36), primary_key=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('disabled', sa.Boolean, default=False),
        mysql_ENGINE='InnoDB',
        mysql_DEFAULT_CHARSET='UTF8'
    )

    op.create_table(
        'rule_conditions',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('rule', sa.String(36), sa.ForeignKey('rules.uuid')),
        sa.Column('op', sa.String(255), nullable=False),
        sa.Column('multiple', sa.String(255), nullable=False),
        sa.Column('field', sa.Text),
        sa.Column('params', types.JsonEncodedDict),
        mysql_ENGINE='InnoDB',
        mysql_DEFAULT_CHARSET='UTF8'
    )

    op.create_table(
        'rule_actions',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('rule', sa.String(36), sa.ForeignKey('rules.uuid')),
        sa.Column('action', sa.String(255), nullable=False),
        sa.Column('params', types.JsonEncodedDict),
        mysql_ENGINE='InnoDB',
        mysql_DEFAULT_CHARSET='UTF8'
    )
