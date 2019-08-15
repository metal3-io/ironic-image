# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.


import mock

from ironic_inspector import db
from ironic_inspector.test import base as test_base


class TestDB(test_base.NodeTest):
    @mock.patch.object(db, 'get_reader_session', autospec=True)
    def test_model_query(self, mock_reader):
        mock_session = mock_reader.return_value
        fake_query = mock_session.query.return_value

        query = db.model_query('db.Node')

        mock_reader.assert_called_once_with()
        mock_session.query.assert_called_once_with('db.Node')
        self.assertEqual(fake_query, query)

    @mock.patch.object(db, 'get_writer_session', autospec=True)
    def test_ensure_transaction_new_session(self, mock_writer):
        mock_session = mock_writer.return_value

        with db.ensure_transaction() as session:
            mock_writer.assert_called_once_with()
            mock_session.begin.assert_called_once_with(subtransactions=True)
            self.assertEqual(mock_session, session)

    @mock.patch.object(db, 'get_writer_session', autospec=True)
    def test_ensure_transaction_session(self, mock_writer):
        mock_session = mock.MagicMock()

        with db.ensure_transaction(session=mock_session) as session:
            self.assertFalse(mock_writer.called)
            mock_session.begin.assert_called_once_with(subtransactions=True)
            self.assertEqual(mock_session, session)

    @mock.patch.object(db.enginefacade, 'transaction_context', autospec=True)
    def test__create_context_manager(self, mock_cnxt):
        mock_ctx_mgr = mock_cnxt.return_value

        ctx_mgr = db._create_context_manager()

        mock_ctx_mgr.configure.assert_called_once_with(sqlite_fk=False)
        self.assertEqual(mock_ctx_mgr, ctx_mgr)

    @mock.patch.object(db, 'get_context_manager', autospec=True)
    def test_get_reader_session(self, mock_cnxt_mgr):
        mock_cnxt = mock_cnxt_mgr.return_value
        mock_sess_maker = mock_cnxt.reader.get_sessionmaker.return_value

        session = db.get_reader_session()

        mock_sess_maker.assert_called_once_with()
        self.assertEqual(mock_sess_maker.return_value, session)

    @mock.patch.object(db, 'get_context_manager', autospec=True)
    def test_get_writer_session(self, mock_cnxt_mgr):
        mock_cnxt = mock_cnxt_mgr.return_value
        mock_sess_maker = mock_cnxt.writer.get_sessionmaker.return_value

        session = db.get_writer_session()

        mock_sess_maker.assert_called_once_with()
        self.assertEqual(mock_sess_maker.return_value, session)
