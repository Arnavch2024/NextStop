import pytest

from app.db.schema_check import MissingMigrationError, check_database_schema


def test_schema_check_missing_migration_009(monkeypatch):
    """check_database_schema raises MissingMigrationError naming 009_day5_consent.sql when Day 5 schema is absent."""
    from unittest.mock import MagicMock

    monkeypatch.setattr("app.db.schema_check.should_skip_schema_check", lambda: False)
    mock_client = MagicMock()

    # Pass Day 3, 4, 6 checks
    def mock_table(table_name):
        builder = MagicMock()
        if table_name == "reference_authorizations":
            builder.select.return_value.limit.return_value.execute.side_effect = Exception("Table not found")
        else:
            builder.select.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        return builder

    mock_client.table.side_effect = mock_table

    with pytest.raises(MissingMigrationError) as exc_info:
        check_database_schema(client=mock_client, raise_on_error=True)

    assert "009_day5_consent.sql" in str(exc_info.value)
