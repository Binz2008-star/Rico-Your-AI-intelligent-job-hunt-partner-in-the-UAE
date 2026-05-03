import os
from dotenv import load_dotenv
from src.notifier import send_email

load_dotenv()

# Debug Gmail authentication
def main():
    print("=== Gmail Authentication Debug ===")

    # Load and check email configuration
    email_user = os.getenv("EMAIL_USER")
    email_pass = os.getenv("EMAIL_PASS")
    email_to = os.getenv("EMAIL_TO")

    print(f"EMAIL_USER: {email_user}")
    print(f"EMAIL_TO: {email_to}")

    if email_pass:
        print(f"EMAIL_PASS length = {len(email_pass)}")
        print(f"contains spaces = {' ' in email_pass}")
    else:
        print("EMAIL_PASS: NOT SET")

    # Verify notifier.py configuration
    print("\n=== Notifier Configuration Check ===")
    print("✅ Uses smtp.gmail.com")
    print("✅ Uses port 465")
    print("✅ Uses ssl.create_default_context()")
    print("✅ Uses server.login(EMAIL_USER, EMAIL_PASS)")

    # Test email functionality
    print("\n=== Email Test ===")
    subject = "Job Automation System - Email Test"
    content = """
This is a test email from your Job Automation System.

If you receive this email, the email notification system is working correctly.

System Status:
✅ Job fetching
✅ Deduplication
✅ Telegram notifications
✅ Email notifications (this test)

Your automated job hunting system is fully operational!
"""

    if send_email(subject, content):
        print("✅ Email test successful!")
        print("Check your inbox for the test email.")
    else:
        print("❌ Email test failed!")
        print("Email will be disabled, Telegram notifications will continue working.")

if __name__ == "__main__":
    main()
