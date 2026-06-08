#!/usr/bin/env python3
"""Simple manual login for Indeed with timeout"""

from playwright.sync_api import sync_playwright
import time

def main():
    print("Opening browser for Indeed login...")
    print("Please log in to Indeed in the browser window.")
    print("Browser will close automatically after 120 seconds.")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.goto('https://ae.indeed.com')

        print("Browser opened. Logging in...")
        for i in range(120):
            time.sleep(1)
            if i % 10 == 0:
                print(f"{120-i}s remaining...")

        print("Closing browser...")
        context.close()
        browser.close()
        print("Done.")

if __name__ == "__main__":
    main()
