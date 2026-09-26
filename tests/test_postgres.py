import os
import pytest
from ola_agent.database import Database

pytestmark=pytest.mark.skipif(os.getenv('TEST_POSTGRES')!='1',reason='Start the project PostgreSQL container and set TEST_POSTGRES=1')


def test_postgres_permissions_and_read_only_transaction(monkeypatch):
    db=Database(url='postgresql+psycopg://demo_reader:demo_reader_local@localhost:5433/ola_demo')
    assert db.query('SELECT COUNT(*) FROM rides')['rows']==[[1200]]
    monkeypatch.setattr('ola_agent.database.validate_sql',lambda sql,dialect:sql)
    from sqlalchemy.exc import DBAPIError
    with pytest.raises(DBAPIError):db.query('DELETE FROM rides')
    assert db.query('SELECT COUNT(*) FROM rides')['rows']==[[1200]]
