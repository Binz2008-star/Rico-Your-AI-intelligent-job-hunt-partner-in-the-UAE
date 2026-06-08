import pytest

from src.rico_chat_api import RicoChatAPI, _SETTINGS_COMMAND_RE


@pytest.mark.parametrize("msg", [
    "Software Engineer", "Senior Backend Developer", "Data Scientist",
    "UX/UI Designer", "C++ Developer", "DevOps Lead", "QA Engineer",
    "Doctor", "Registered Nurse", "Cardiologist", "Surgeon",
    "Médico", "Physician Assistant",
    "Accountant", "Chief Financial Officer", "Investment Analyst",
    "Tax Consultant", "Auditor",
    "Chef", "Pastry Chef", "Chef de Cuisine", "Electrician",
    "Photographer", "Graphic Designer", "Pilot", "Architect",
    "HSE Manager", "QHSE Officer", "Environmental Engineer",
    "CEO", "CTO", "CFO",
    "Senior Vice President of Global Marketing",
])
def test_accepts_real_role_titles(msg: str) -> None:
    assert RicoChatAPI._looks_like_bare_target_role(msg) is True


@pytest.mark.parametrize("msg", [
    "what is my status", "What is my status?",
    "how are you", "why do I get no matches",
    "where are the jobs", "when will you reply",
    "which one is best", "is there anything new",
    "qué jobs hay?", "状态怎么样？",
    "tell me jobs", "show me openings", "find me a role",
    "give me matches", "list my applications", "help me please",
    "explain this", "describe the position",
    "hi", "hello there", "hey", "thanks", "ok cool", "yes please",
    "no thanks", "great",
    "my status", "I want jobs", "I'm looking", "we need help",
    "the manager position", "any new jobs", "some openings",
    "manager 5 years", "engineer level 2",
    "a really specific senior staff principal software engineer position",
    "Hello. Find jobs.",
    "", "   ",
])
def test_rejects_non_role_messages(msg: str) -> None:
    assert RicoChatAPI._looks_like_bare_target_role(msg) is False


# Location-only messages must never be treated as job role titles.
@pytest.mark.parametrize("msg", [
    "UAE",
    "Dubai",
    "Abu Dhabi",
    "Sharjah",
    "Ajman",
    "jobs in UAE",
    "UAE jobs",
    "jobs in Dubai",
    "Dubai jobs",
    "roles in UAE",
    "job in the UAE",
    "a job in Dubai",
])
def test_rejects_location_only_messages(msg: str) -> None:
    assert RicoChatAPI._looks_like_bare_target_role(msg) is False, (
        f"Expected _looks_like_bare_target_role({msg!r}) to be False — "
        "location names are not job roles"
    )


# Email addresses are never job roles — they are usually answers to a prompt
# (e.g. "what's the company email?"). They must not trigger a role-search error.
@pytest.mark.parametrize("msg", [
    "info@liongold.com",
    "ahmed@example.com",
    "careers@company.co.uk",
    "My email is info@liongold.com",
])
def test_rejects_email_addresses(msg: str) -> None:
    assert RicoChatAPI._looks_like_bare_target_role(msg) is False, (
        f"Expected _looks_like_bare_target_role({msg!r}) to be False — "
        "an email address is not a job role"
    )


# Imperative settings / notification commands are not job roles.
@pytest.mark.parametrize("msg", [
    "enable telegram notifications",
    "disable notifications",
    "turn off email alerts",
    "activate reminders",
    "mute alerts",
])
def test_rejects_settings_commands(msg: str) -> None:
    assert RicoChatAPI._looks_like_bare_target_role(msg) is False, (
        f"Expected _looks_like_bare_target_role({msg!r}) to be False — "
        "a settings command is not a job role"
    )


class TestSettingsCommandRegex:
    @pytest.mark.parametrize("msg", [
        "enable telegram notifications",
        "Enable Telegram Notifications",
        "turn on notifications",
        "turn off email alerts",
        "disable reminders",
        "deactivate whatsapp alerts",
        "mute notifications",
        "stop sending me alerts",
    ])
    def test_matches_settings_commands(self, msg: str) -> None:
        assert _SETTINGS_COMMAND_RE.search(msg) is not None

    @pytest.mark.parametrize("msg", [
        "HSE Manager",
        "find me jobs in Dubai",
        "enable me to grow",          # no notification noun
        "telegram",                    # no command verb
        "what are my notifications",   # a question, not a command
    ])
    def test_does_not_match_non_commands(self, msg: str) -> None:
        assert _SETTINGS_COMMAND_RE.search(msg) is None


# Mixed role+location messages with a real role still pass (role extraction is separate).
@pytest.mark.parametrize("msg", [
    "HSE Manager",
    "Environmental Compliance Officer",
    "Safety Engineer",
])
def test_accepts_role_title_even_when_uae_context_nearby(msg: str) -> None:
    # The role title alone (without location noise) should still be accepted.
    assert RicoChatAPI._looks_like_bare_target_role(msg) is True
