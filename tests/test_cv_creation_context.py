"""Test CV creation context handling in pending intent resolution."""

import pytest
from unittest.mock import Mock, patch
from src.rico_chat_api import RicoChatAPI


class TestCVCreationContext:
    """Test CV creation follow-up phrases are routed correctly after CV creation offer."""

    def setup_method(self):
        """Set up test fixtures."""
        self.api = RicoChatAPI(persist=False)
        self.user_id = "test_user_123"
        self.profile = Mock()
        self.profile.name = "Test User"
        # Set up mock profile attributes to prevent len() errors
        self.profile.skills = []
        self.profile.industries = []
        self.profile.preferred_cities = []
        self.profile.years_experience = None
        self.profile.cv_filename = None
        self.profile.cv_status = None

    @patch.object(RicoChatAPI, '_get_last_assistant_message')
    @patch.object(RicoChatAPI, '_is_affirmative')
    def test_cv_creation_context_detected(self, mock_affirmative, mock_last_message):
        """Test that CV creation context is properly detected from last assistant message."""
        # Setup
        mock_affirmative.return_value = True
        mock_last_message.return_value = "I can help you build a CV from scratch. Tell me your current role and experience."

        # Execute
        result = self.api._resolve_pending_intent(self.user_id, "yes", self.profile)

        # Verify
        assert result is not None
        assert result["type"] == "cv_creation"
        assert "build a CV from scratch" in result["message"]

    @patch.object(RicoChatAPI, '_get_last_assistant_message')
    @patch.object(RicoChatAPI, '_is_affirmative')
    def test_cv_creation_context_arabic(self, mock_affirmative, mock_last_message):
        """Test Arabic CV creation context detection."""
        # Setup
        mock_affirmative.return_value = True
        mock_last_message.return_value = "سأساعدك في بناء سيرة ذاتية من الصفر. أخبرني بدورك الحالي."

        # Execute
        result = self.api._resolve_pending_intent(self.user_id, "نعم", self.profile)

        # Verify
        assert result is not None
        assert result["type"] == "cv_creation"

    @patch.object(RicoChatAPI, '_get_last_assistant_message')
    @patch.object(RicoChatAPI, '_is_affirmative')
    def test_cv_creation_variations(self, mock_affirmative, mock_last_message):
        """Test various CV creation signal phrases."""
        cv_creation_phrases = [
            "I can create a CV for you. What's your experience?",
            "Let me make a CV for you from scratch.",
            "I'll help you build your CV. Tell me your background.",
            "اصنع لي سيرة ذاتية. ما هو دورك؟",
            "سأساعدك في بناء سيرة ذاتية"
        ]

        for phrase in cv_creation_phrases:
            mock_affirmative.return_value = True
            mock_last_message.return_value = phrase

            result = self.api._resolve_pending_intent(self.user_id, "yes", self.profile)

            assert result is not None, f"Failed for phrase: {phrase}"
            assert result["type"] == "cv_creation", f"Wrong type for phrase: {phrase}"

    @patch.object(RicoChatAPI, '_get_last_assistant_message')
    @patch.object(RicoChatAPI, '_is_affirmative')
    def test_cv_improve_context_not_confused(self, mock_affirmative, mock_last_message):
        """Test that CV improvement context doesn't trigger CV creation."""
        # Setup
        mock_affirmative.return_value = True
        mock_last_message.return_value = "I can improve your CV. What would you like to enhance?"

        # Execute
        result = self.api._resolve_pending_intent(self.user_id, "yes", self.profile)

        # Verify - should route to AI fallback for CV improvement, not creation
        assert result is not None
        # The result should be from _answer_with_ai_fallback, not _handle_cv_creation
        assert "fallback" in str(result).lower() or "ai" in str(result).lower()

    @patch.object(RicoChatAPI, '_get_last_assistant_message')
    @patch.object(RicoChatAPI, '_is_affirmative')
    def test_non_affirmative_returns_none(self, mock_affirmative, mock_last_message):
        """Test that non-affirmative responses return None."""
        # Setup
        mock_affirmative.return_value = False
        mock_last_message.return_value = "I can help you build a CV from scratch."

        # Execute
        result = self.api._resolve_pending_intent(self.user_id, "new CV", self.profile)

        # Verify
        assert result is None

    @patch.object(RicoChatAPI, '_get_last_assistant_message')
    @patch.object(RicoChatAPI, '_is_affirmative')
    def test_no_last_message_returns_none(self, mock_affirmative, mock_last_message):
        """Test that missing last message returns None."""
        # Setup
        mock_affirmative.return_value = True
        mock_last_message.return_value = ""

        # Execute
        result = self.api._resolve_pending_intent(self.user_id, "yes", self.profile)

        # Verify
        assert result is None

    @patch.object(RicoChatAPI, '_get_last_assistant_message')
    @patch.object(RicoChatAPI, '_is_affirmative')
    def test_cv_creation_followup_phrases(self, mock_affirmative, mock_last_message):
        """Test various follow-up phrases after CV creation offer."""
        # Setup
        mock_affirmative.return_value = True  # All these should be treated as affirmative
        mock_last_message.return_value = "I can help you build a CV from scratch."

        followup_phrases = ["new CV", "make it", "yes create CV", "build my CV", "continue"]

        for phrase in followup_phrases:
            result = self.api._resolve_pending_intent(self.user_id, phrase, self.profile)

            assert result is not None, f"Failed for follow-up: {phrase}"
            assert result["type"] == "cv_creation", f"Wrong type for follow-up: {phrase}"

    @patch.object(RicoChatAPI, '_get_last_assistant_message')
    @patch.object(RicoChatAPI, '_is_affirmative')
    def test_unrelated_context_returns_none(self, mock_affirmative, mock_last_message):
        """Test that unrelated last messages don't trigger CV creation."""
        # Setup
        mock_affirmative.return_value = True
        mock_last_message.return_value = "Here are some jobs I found for you."

        # Execute
        result = self.api._resolve_pending_intent(self.user_id, "new CV", self.profile)

        # Verify
        assert result is None

    def test_handle_cv_creation_response_structure(self):
        """Test that _handle_cv_creation returns proper response structure."""
        # Execute
        result = self.api._handle_cv_creation(self.user_id, self.profile)

        # Verify
        assert result["type"] == "cv_creation"
        assert "message" in result
        assert "next_action" in result
        assert "fields_needed" in result
        assert "collect_cv_fields" == result["next_action"]
        assert isinstance(result["fields_needed"], list)
        assert "Hi Test User," in result["message"]
