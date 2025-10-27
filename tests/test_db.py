import pytest
from sqlalchemy import text

from quizbot.db import engine, init_db, _set_sqlite_pragma


@pytest.mark.asyncio
async def test_init_db_creates_schema_and_enables_fk():
    await init_db()
    async with engine.connect() as conn:
        # foreign keys pragma should be enabled via connect listener
        result = await conn.execute(text("PRAGMA foreign_keys"))
        assert result.scalar() == 1

        tables = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        table_names = {row[0] for row in tables}
        assert {"teams", "team_members", "games", "rounds"}.issubset(table_names)


def test_sqlite_pragma_handles_errors():
    class DummyConn:
        def cursor(self):
            raise RuntimeError("boom")

    # Не должно выбрасывать исключение
    _set_sqlite_pragma(DummyConn(), None)
