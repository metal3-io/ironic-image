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

"""attribute_constraints_relaxing

Revision ID: 882b2d84cb1b
Revises: d00d6e3f38c4
Create Date: 2017-01-13 11:27:00.053286

"""

from alembic import op
from oslo_utils import uuidutils
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector as insp


# revision identifiers, used by Alembic.
revision = '882b2d84cb1b'
down_revision = 'd00d6e3f38c4'
branch_labels = None
depends_on = None

ATTRIBUTES = 'attributes'
NODES = 'nodes'
NAME = 'name'
VALUE = 'value'
UUID = 'uuid'
NODE_UUID = 'node_uuid'

naming_convention = {
    "pk": 'pk_%(table_name)s',
    "fk": 'fk_%(table_name)s'
}


def upgrade():

    connection = op.get_bind()

    inspector = insp.from_engine(connection)

    pk_constraint = (inspector.get_pk_constraint(ATTRIBUTES).get('name')
                     or naming_convention['pk'] % {'table_name': ATTRIBUTES})
    fk_constraint = (inspector.get_foreign_keys(ATTRIBUTES)[0].get('name')
                     or naming_convention['fk'] % {'table_name': ATTRIBUTES})

    columns_meta = inspector.get_columns(ATTRIBUTES)
    name_type = {meta.get('type') for meta in columns_meta
                 if meta['name'] == NAME}.pop()
    value_type = {meta.get('type') for meta in columns_meta
                  if meta['name'] == VALUE}.pop()

    node_uuid_column = sa.Column(NODE_UUID, sa.String(36))
    op.add_column(ATTRIBUTES, node_uuid_column)

    attributes = sa.table(ATTRIBUTES, node_uuid_column,
                          sa.Column(UUID, sa.String(36)))

    with op.batch_alter_table(ATTRIBUTES,
                              naming_convention=naming_convention) as batch_op:
        batch_op.drop_constraint(fk_constraint, type_='foreignkey')

    rows = connection.execute(sa.select([attributes.c.uuid,
                                         attributes.c.node_uuid]))

    for row in rows:
        # move uuid to node_uuid, reuse uuid as a new primary key
        connection.execute(
            attributes.update().where(attributes.c.uuid == row.uuid).
            values(node_uuid=row.uuid, uuid=uuidutils.generate_uuid())
        )

    with op.batch_alter_table(ATTRIBUTES,
                              naming_convention=naming_convention) as batch_op:
        batch_op.drop_constraint(pk_constraint, type_='primary')
        batch_op.create_primary_key(pk_constraint, [UUID])
        batch_op.create_foreign_key('fk_node_attribute', NODES,
                                    [NODE_UUID], [UUID])
        batch_op.alter_column('name', nullable=False, type_=name_type)
        batch_op.alter_column('value', nullable=True, type_=value_type)
