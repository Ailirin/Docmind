"""Unit-тест слоя хранилища: SQL-statement содержит LIMIT и OFFSET."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.storage.documents import list_documents


@pytest.mark.asyncio
async def test_list_documents_applies_limit_offset():
    """list_documents передаёт limit/offset в SQL-statement."""
    captured: list = []

    async def _fake_scalars(stmt):
        captured.append(stmt)
        result = MagicMock()
        result.all.return_value = []
        return result

    db = AsyncMock()
    db.scalars.side_effect = _fake_scalars

    await list_documents(db, limit=10, offset=20)

    assert captured, "db.scalars не был вызван"
    compiled = captured[0].compile()
    sql = str(compiled).lower()
    assert "limit" in sql
    assert "offset" in sql
