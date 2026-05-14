"""End-to-end tests for Jotform integration without mocks."""

import os
import pytest

from src.rico_jotform_webhook import _active_form_ids


class TestJotformFormIdHandling:
    """Test Jotform form ID handling end-to-end."""

    def test_active_form_ids_with_jotform_form_id_only(self, monkeypatch):
        """_active_form_ids accepts JOTFORM_FORM_ID."""
        monkeypatch.setenv("JOTFORM_FORM_ID", "261277622782059")
        monkeypatch.delenv("JOTFORM_RICO_FORM_ID", raising=False)
        
        ids = _active_form_ids()
        assert "261277622782059" in ids
        assert len(ids) == 1

    def test_active_form_ids_with_jotform_rico_form_id_only(self, monkeypatch):
        """_active_form_ids accepts JOTFORM_RICO_FORM_ID alias."""
        monkeypatch.delenv("JOTFORM_FORM_ID", raising=False)
        monkeypatch.setenv("JOTFORM_RICO_FORM_ID", "261277705943060")
        
        ids = _active_form_ids()
        assert "261277705943060" in ids
        assert len(ids) == 1

    def test_active_form_ids_with_both_env_vars(self, monkeypatch):
        """_active_form_ids accepts both JOTFORM_FORM_ID and JOTFORM_RICO_FORM_ID."""
        monkeypatch.setenv("JOTFORM_FORM_ID", "261277622782059")
        monkeypatch.setenv("JOTFORM_RICO_FORM_ID", "261277705943060")
        
        ids = _active_form_ids()
        assert "261277622782059" in ids
        assert "261277705943060" in ids
        assert len(ids) == 2

    def test_active_form_ids_with_comma_separated(self, monkeypatch):
        """_active_form_ids accepts comma-separated JOTFORM_FORM_ID."""
        monkeypatch.setenv("JOTFORM_FORM_ID", "261277622782059,261277705943060")
        monkeypatch.delenv("JOTFORM_RICO_FORM_ID", raising=False)
        
        ids = _active_form_ids()
        assert "261277622782059" in ids
        assert "261277705943060" in ids
        assert len(ids) == 2

    def test_active_form_ids_empty_when_not_configured(self, monkeypatch):
        """_active_form_ids returns empty set when neither env var is set."""
        monkeypatch.delenv("JOTFORM_FORM_ID", raising=False)
        monkeypatch.delenv("JOTFORM_RICO_FORM_ID", raising=False)
        
        ids = _active_form_ids()
        assert len(ids) == 0

    def test_active_form_ids_whitespace_handling(self, monkeypatch):
        """_active_form_ids trims whitespace from form IDs."""
        monkeypatch.setenv("JOTFORM_FORM_ID", " 261277622782059 , 261277705943060 ")
        monkeypatch.delenv("JOTFORM_RICO_FORM_ID", raising=False)
        
        ids = _active_form_ids()
        assert "261277622782059" in ids
        assert "261277705943060" in ids
        assert len(ids) == 2
