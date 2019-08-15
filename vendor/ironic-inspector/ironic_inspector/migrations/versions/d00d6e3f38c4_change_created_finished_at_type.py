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

"""Change created|finished_at type to DateTime

Revision ID: d00d6e3f38c4
Revises: d2e48801c8ef
Create Date: 2016-12-15 17:18:10.728695

"""

import datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd00d6e3f38c4'
down_revision = 'd2e48801c8ef'
branch_labels = None
depends_on = None


def upgrade():
    started_at = sa.Column('started_at', sa.types.Float, nullable=True)
    finished_at = sa.Column('finished_at', sa.types.Float, nullable=True)
    temp_started_at = sa.Column("temp_started_at", sa.types.DateTime,
                                nullable=True)
    temp_finished_at = sa.Column("temp_finished_at", sa.types.DateTime,
                                 nullable=True)
    uuid = sa.Column("uuid", sa.String(36), primary_key=True)

    op.add_column("nodes", temp_started_at)
    op.add_column("nodes", temp_finished_at)

    t = sa.table('nodes', started_at, finished_at,
                 temp_started_at, temp_finished_at, uuid)

    conn = op.get_bind()
    rows = conn.execute(sa.select([t.c.started_at, t.c.finished_at, t.c.uuid]))
    for row in rows:
        temp_started = datetime.datetime.utcfromtimestamp(row['started_at'])
        temp_finished = row['finished_at']
        # Note(milan) this is just a precaution; sa.null shouldn't happen here
        if temp_finished is not None:
            temp_finished = datetime.datetime.utcfromtimestamp(temp_finished)
        conn.execute(t.update().where(t.c.uuid == row.uuid).values(
            temp_started_at=temp_started, temp_finished_at=temp_finished))

    with op.batch_alter_table('nodes') as batch_op:
        batch_op.drop_column('started_at')
        batch_op.drop_column('finished_at')
        batch_op.alter_column('temp_started_at',
                              existing_type=sa.types.DateTime,
                              nullable=True,
                              new_column_name='started_at')
        batch_op.alter_column('temp_finished_at',
                              existing_type=sa.types.DateTime,
                              nullable=True,
                              new_column_name='finished_at')
