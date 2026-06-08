#!/usr/bin/env python3
"""Simple manual login for Indeed - non-persistent context"""

from playwright.sync_api import sync_playwright
import time

def main():
    print("Opening browser for Indeed login (simple mode)...")
    print("Please log in to Indeed in the browser window.")
    print("Press ENTER in this terminal when you're done to close the browser.")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.goto('https://ae.indeed.com')

        print("Browser opened. Please log in now...")
        print("Press ENTER when done...")
        input()

        print("Closing browser...")
        context.close()
        browser.close()
        print("Done. Note: This session won't be saved (non-persistent mode).")

if __name__ == "__main__":
    main()
