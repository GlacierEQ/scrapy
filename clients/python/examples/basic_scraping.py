"""
Basic Scraping Examples

This script demonstrates how to use the Scrapy client library
to perform basic scraping operations.
"""

import os
import json
import logging
from pprint import pprint
import sys

# Add parent directory to path to import the client
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scrapy_client import ScrapyClient, ScrapyAPIError

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Run basic scraping examples."""
    # Get API key from environment variable
    api_key = os.environ.get('SCRAPY_API_KEY')
    
    if not api_key:
        logger.warning("SCRAPY_API_KEY environment variable not set. Using demo mode.")
        # In demo mode, we'll use a fake API key that should work with local development server
        api_key = "demo_key_for_local_development"
    
    # Initialize client
    client = ScrapyClient(
        base_url="http://localhost:8000/api",
        api_key=api_key
    )
    
    try:
        # Test connection
        logger.info("Testing API connection...")
        status = client.get_status()
        print("API Status:")
        pprint(status)
        print("\n")
        
        # Simple scrape
        logger.info("Performing simple scrape...")
        simple_result = client.simple_scrape(
            url="https://example.com",
            compile_text=True,
            screenshot=True
        )
        print("Simple Scrape Result:")
        pprint(simple_result)
        print("\n")
        
        # Adaptive scrape (synchronous)
        logger.info("Performing adaptive scrape...")
        adaptive_result = client.adaptive_scrape(
            url="https://news.ycombinator.com",
            data_type="list",
            use_ai=False,
            async_task=False  # Run synchronously
        )
        print("Adaptive Scrape Result:")
        pprint(adaptive_result)
        print("\n")
        
        # Recursive scrape with waiting
        logger.info("Performing recursive scrape (with waiting)...")
        recursive_result = client.scrape_and_wait(
            url="https://quotes.toscrape.com",
            scrape_type="recursive",
            timeout=120,  # Wait up to 2 minutes
            max_depth=2,
            max_pages=10,
            same_domain=True
        )
        print("Recursive Scrape Result:")
        pprint(recursive_result)
        print("\n")
        
        # List our recent tasks
        logger.info("Listing recent tasks...")
        tasks = client.list_tasks(limit=5)
        print("Recent Tasks:")
        pprint(tasks)
        print("\n")
        
    except ScrapyAPIError as e:
        logger.error(f"API Error: {e.message} (Code: {e.code}, Status: {e.status_code})")
        if e.response:
            logger.debug(f"Response details: {e.response}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")

if __name__ == "__main__":
    main()
