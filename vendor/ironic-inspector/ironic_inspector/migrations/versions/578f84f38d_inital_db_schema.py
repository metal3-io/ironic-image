# Copyright 2015 Cisco Systems, Inc.
# All rights reserved.
#
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
#

"""inital_db_schema

Revision ID: 578f84f38d
Revises:
Create Date: 2015-09-15 14:52:22.448944

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '578f84f38d'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'nodes',
        sa.Column('uuid', sa.String(36), primary_key=True),
        sa.Column('started_at', sa.Float, nullable=True),
        sa.Column('finished_at', sa.Float, nullable=True),
        sa.Column('error', sa.Text, nullable=True),
        mysql_ENGINE='InnoDB',
        mysql_DEFAULT_CHARSET='UTF8'
    )

    op.create_table(
        'attributes',
        sa.Column('name', sa.String(255), primary_key=True),
        sa.Column('value', sa.String(255), primary_key=True),
        sa.Column('uuid', sa.String(36), sa.ForeignKey('nodes.uuid')),
        mysql_ENGINE='InnoDB',
        mysql_DEFAULT_CHARSET='UTF8'
    )

    op.create_table(
        'options',
        sa.Column('uuid', sa.String(36), sa.ForeignKey('nodes.uuid'),
                  primary_key=True),
        sa.Column('name', sa.String(255), primary_key=True),
        sa.Column('value', sa.Text),
        mysql_ENGINE='InnoDB',
        mysql_DEFAULT_CHARSET='UTF8'
    )
