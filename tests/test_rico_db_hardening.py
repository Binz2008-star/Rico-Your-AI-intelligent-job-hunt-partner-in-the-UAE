"""Tests for Rico DB hardening - pagination clamps, status validation, and duplicate prevention."""
import pytest
from src.rico_db import RicoDB


class TestPaginationClamps:
    """Test pagination parameter clamping."""

    def test_clamp_limit_clamps_above_max(self):
        """Clamp limit above MAX_RECOMMENDATION_LIMIT."""
        assert RicoDB._clamp_limit(200) == RicoDB.MAX_RECOMMENDATION_LIMIT
        assert RicoDB._clamp_limit(1000) == RicoDB.MAX_RECOMMENDATION_LIMIT

    def test_clamp_limit_clamps_negative_to_default(self):
        """Clamp negative limit to default."""
        assert RicoDB._clamp_limit(-10) == RicoDB.DEFAULT_RECOMMENDATION_LIMIT
        assert RicoDB._clamp_limit(0) == RicoDB.DEFAULT_RECOMMENDATION_LIMIT

    def test_clamp_limit_clamps_invalid_to_default(self):
        """Clamp invalid limit to default."""
        assert RicoDB._clamp_limit("invalid") == RicoDB.DEFAULT_RECOMMENDATION_LIMIT
        assert RicoDB._clamp_limit(None) == RicoDB.DEFAULT_RECOMMENDATION_LIMIT

    def test_clamp_offset_clamps_negative_to_zero(self):
        """Clamp negative offset to zero."""
        assert RicoDB._clamp_offset(-10) == 0
        assert RicoDB._clamp_offset(-1) == 0

    def test_clamp_offset_clamps_invalid_to_zero(self):
        """Clamp invalid offset to zero."""
        assert RicoDB._clamp_offset("invalid") == 0
        assert RicoDB._clamp_offset(None) == 0

    def test_clamp_offset_preserves_valid(self):
        """Preserve valid offset values."""
        assert RicoDB._clamp_offset(0) == 0
        assert RicoDB._clamp_offset(10) == 10
        assert RicoDB._clamp_offset(100) == 100


class TestStatusValidation:
    """Test status validation in get_recommendations and update_recommendation_status."""

    def test_get_recommendations_rejects_invalid_status(self):
        """get_recommendations returns empty list for invalid status."""
        db = RicoDB()
        if not db.available:
            pytest.skip("DATABASE_URL not available")
        
        # Use a fake user_id that won't exist
        result = db.get_recommendations("test-user-123", status="invalid_status")
        assert result == []

    def test_update_recommendation_status_rejects_invalid_status(self):
        """update_recommendation_status raises ValueError for invalid status."""
        db = RicoDB()
        if not db.available:
            pytest.skip("DATABASE_URL not available")
        
        with pytest.raises(ValueError) as exc_info:
            db.update_recommendation_status("test-user-123", "job-key-123", "invalid_status")
        
        assert "Invalid recommendation status" in str(exc_info.value)

    def test_update_recommendation_status_accepts_valid_statuses(self):
        """update_recommendation_status accepts all valid statuses."""
        db = RicoDB()
        if not db.available:
            pytest.skip("DATABASE_URL not available")
        
        # This should not raise ValueError for valid statuses
        valid_statuses = ["found", "saved", "applied", "skipped", "blocked", "decision_made", "interview", "rejected", "offer"]
        for status in valid_statuses:
            # We expect this to fail because user/job doesn't exist, but not due to validation
            try:
                db.update_recommendation_status("test-user-123", "job-key-123", status)
            except ValueError as e:
                if "Invalid recommendation status" in str(e):
                    pytest.fail(f"Valid status {status} was rejected")
            except Exception:
                # Expected - user/job doesn't exist
                pass


class TestDuplicatePrevention:
    """Test ON CONFLICT handling in save_recommendations."""

    def test_save_recommendations_upserts_same_user_job_key(self):
        """save_recommendations upserts instead of duplicating same user/job_key."""
        db = RicoDB()
        if not db.available:
            pytest.skip("DATABASE_URL not available")
        
        # Create a test user
        user = db.upsert_user({"external_user_id": "test-dup-user", "email": "test@example.com"})
        user_id = user["id"]
        
        # Save a recommendation
        job = {"title": "Test Job", "company": "Test Company", "link": "https://example.com/job1"}
        matches = [{"job": job, "job_key": "job1", "repo_score": 80, "rico_score": 90}]
        db.save_recommendations(user_id, matches)
        
        # Get initial count
        recs1 = db.get_recommendations(user_id)
        initial_count = len(recs1)
        
        # Save the same recommendation again (should upsert, not duplicate)
        db.save_recommendations(user_id, matches)
        
        # Verify count hasn't changed
        recs2 = db.get_recommendations(user_id)
        assert len(recs2) == initial_count
        
        # Cleanup
        with db.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM rico_job_recommendations WHERE user_id = %s", (user_id,))
                cur.execute("DELETE FROM rico_users WHERE id = %s", (user_id,))
            conn.commit()

    def test_different_users_can_have_same_job_key(self):
        """Same job_key can exist for different users."""
        db = RicoDB()
        if not db.available:
            pytest.skip("DATABASE_URL not available")
        
        # Create two test users
        user1 = db.upsert_user({"external_user_id": "test-dup-user-1", "email": "test1@example.com"})
        user2 = db.upsert_user({"external_user_id": "test-dup-user-2", "email": "test2@example.com"})
        
        user1_id = user1["id"]
        user2_id = user2["id"]
        
        # Save the same job for both users
        job = {"title": "Test Job", "company": "Test Company", "link": "https://example.com/job1"}
        matches = [{"job": job, "job_key": "job1", "repo_score": 80, "rico_score": 90}]
        
        db.save_recommendations(user1_id, matches)
        db.save_recommendations(user2_id, matches)
        
        # Both should have the recommendation
        recs1 = db.get_recommendations(user1_id)
        recs2 = db.get_recommendations(user2_id)
        
        assert len(recs1) == 1
        assert len(recs2) == 1
        
        # Cleanup
        with db.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM rico_job_recommendations WHERE user_id = %s", (user1_id,))
                cur.execute("DELETE FROM rico_job_recommendations WHERE user_id = %s", (user2_id,))
                cur.execute("DELETE FROM rico_users WHERE id = %s", (user1_id,))
                cur.execute("DELETE FROM rico_users WHERE id = %s", (user2_id,))
            conn.commit()
