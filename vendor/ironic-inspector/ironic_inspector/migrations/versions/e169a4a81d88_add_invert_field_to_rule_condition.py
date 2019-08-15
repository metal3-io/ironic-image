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

"""Add invert field to rule condition

Revision ID: e169a4a81d88
Revises: d588418040d
Create Date: 2016-02-16 11:19:29.715615

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e169a4a81d88'
down_revision = 'd588418040d'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('rule_conditions', sa.Column('invert', sa.Boolean(),
                                               nullable=True, default=False))
