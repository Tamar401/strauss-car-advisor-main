import sqlite3

from tests.conftest import TEST_DATABASE_URL


def test_store_uses_configured_backend(isolated):
    """TEST_DATABASE_URL מוגדר → הבדיקות באמת רצות מול PostgreSQL, לא SQLite בשקט."""
    assert isinstance(isolated._con, sqlite3.Connection) == (TEST_DATABASE_URL is None)


def test_email_lookup_ignores_case(isolated):
    assert isolated.create_user("u1", "Dana@Example.test", "hash")
    assert isolated.user_by_email("dana@example.test")["id"] == "u1"
    assert not isolated.create_user("u2", "DANA@example.test", "hash")
