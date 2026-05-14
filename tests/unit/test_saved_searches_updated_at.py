"""tests/unit/test_saved_searches_updated_at.py

Unit tests for saved-searches updated_at column migration.
Tests the migration that adds updated_at to rico_saved_searches table.
"""
import pytest
import os
from pathlib import Path


class TestSavedSearchesUpdatedAtMigration:
    """Migration 012 must add updated_at column with proper defaults and trigger."""

    def test_migration_file_exists(self):
        """Migration file 012_add_updated_at_to_saved_searches.sql must exist."""
        migration_path = Path("migrations/012_add_updated_at_to_saved_searches.sql")
        assert migration_path.exists()

    def test_migration_adds_column_with_default(self):
        """Migration must add updated_at column with DEFAULT NOW()."""
        migration_path = Path("migrations/012_add_updated_at_to_saved_searches.sql")
        content = migration_path.read_text()
        
        assert "ALTER TABLE rico_saved_searches" in content
        assert "ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()" in content

    def test_migration_updates_existing_rows(self):
        """Migration must set updated_at = created_at for existing rows."""
        migration_path = Path("migrations/012_add_updated_at_to_saved_searches.sql")
        content = migration_path.read_text()
        
        assert "UPDATE rico_saved_searches" in content
        assert "SET updated_at = created_at" in content
        assert "WHERE updated_at IS NULL" in content

    def test_migration_creates_trigger_function(self):
        """Migration must create a function to auto-update updated_at."""
        migration_path = Path("migrations/012_add_updated_at_to_saved_searches.sql")
        content = migration_path.read_text()
        
        assert "CREATE OR REPLACE FUNCTION update_saved_searches_updated_at()" in content
        assert "NEW.updated_at = NOW()" in content
        assert "RETURN NEW" in content

    def test_migration_drops_existing_trigger(self):
        """Migration must drop existing trigger before creating new one."""
        migration_path = Path("migrations/012_add_updated_at_to_saved_searches.sql")
        content = migration_path.read_text()
        
        assert "DROP TRIGGER IF EXISTS trg_saved_searches_updated_at ON rico_saved_searches" in content

    def test_migration_creates_trigger(self):
        """Migration must create trigger to call update function."""
        migration_path = Path("migrations/012_add_updated_at_to_saved_searches.sql")
        content = migration_path.read_text()
        
        assert "CREATE TRIGGER trg_saved_searches_updated_at" in content
        assert "BEFORE UPDATE ON rico_saved_searches" in content
        assert "FOR EACH ROW" in content
        assert "EXECUTE FUNCTION update_saved_searches_updated_at()" in content

    def test_migration_is_idempotent(self):
        """Migration must use IF NOT EXISTS to be idempotent."""
        migration_path = Path("migrations/012_add_updated_at_to_saved_searches.sql")
        content = migration_path.read_text()
        
        assert "IF NOT EXISTS" in content
        assert "DROP TRIGGER IF EXISTS" in content

    def test_migration_has_proper_comments(self):
        """Migration must have comments explaining its purpose."""
        migration_path = Path("migrations/012_add_updated_at_to_saved_searches.sql")
        content = migration_path.read_text()
        
        assert content.startswith("--")
        assert "Neon DB" in content or "compatibility" in content.lower()
