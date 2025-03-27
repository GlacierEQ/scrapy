"""
Examples demonstrating proper error handling techniques in Scrapy.

These examples show best practices for handling various error scenarios
that may occur during web scraping operations.
"""

import logging
import time
from scraping_project.error_handler import retry, error_context, ScrapyError
from scraping_project.resilient_browser import ResilientBrowser
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import requests
from requests.exceptions import RequestException
import json

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def example_error_context():
    """Demonstrate the error_context context manager."""
    # Handle file operations safely
    with error_context("file_reading", reraise=False):
        with open("non_existent_file.txt", "r") as f:
            content = f.read()
            print(f"Content: {content}")

    # Handle network operations with cleanup
    session = requests.Session()
    
    def cleanup_func():
        session.close()
        logger.info("Session closed.")
        
    with error_context("api_request", cleanup_func=cleanup_func):
        response = session.get("https://httpbin.org/status/500")
        response.raise_for_status()

def example_retry_decorator():
    """Demonstrate the retry decorator."""
    @retry(max_tries=3, delay=1.0, exceptions=(RequestException,))
    def fetch_url(url):
        response = requests.get(url)
        response.raise_for_status()
        return response.text
    
    try:
        # This will retry 3 times for connection errors
        content = fetch_url("https://httpbin.org/status/503")
        print(f"Content length: {len(content)}")
    except Exception as e:
        print(f"Final exception: {e}")

def example_browser_error_recovery():
    """Demonstrate browser error recovery."""
    browser = ResilientBrowser(headless=True)
    
    try:
        # Start browser session
        browser.start()
        
        # Navigate to a URL
        browser.get("https://example.com")
        
        # Wait for element with safe recovery
        try:
            element = browser.wait_for(By.TAG_NAME, "h1")
            print(f"Found element: {element.text}")
        except TimeoutException:
            print("Element not found, but browser session remains intact")
        
        # Simulate a problematic click
        try:
            browser.safe_click(browser.driver.find_element(By.TAG_NAME, "nonexistent"))
        except Exception as e:
            print(f"Click failed but handled: {e}")
        
        # Browser still works after error
        browser.get("https://httpbin.org")
        print("Successfully navigated after error recovery")
        
    except Exception as e:
        print(f"Unhandled error: {e}")
    finally:
        browser.close()

def main():
    """Run all examples."""
    print("\n=== Example: Error Context ===")
    example_error_context()
    
    print("\n=== Example: Retry Decorator ===")
    example_retry_decorator()
    
    print("\n=== Example: Browser Error Recovery ===")
    example_browser_error_recovery()

if __name__ == "__main__":
    main()