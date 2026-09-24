from ast import stmt
from unittest.mock import MagicMock

from app.storage.documents import list_documents

def test_list_documents_applies_limit_offset():
    db =  MagicMock()
    db.scalars.return_value.all.return_value = []

    list_documents(db, limit=10, offset=20)

    stmt = db.scalars.call_args[0][0]
    # у Statement есть _limit/_offset в SQLAlchemy 2; проще проверить compile
    compiled = stmt.compile()
    sql = str(compiled).lower()
    assert "limit" in sql
    assert "offset" in sql