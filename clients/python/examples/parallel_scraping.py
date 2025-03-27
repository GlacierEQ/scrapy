"""
Advanced Parallel Scraping Example

This script demonstrates how to use the Scrapy client library
for parallel scraping operations and data processing.
"""

import os
import json
import logging
import time
import pandas as pd
from typing import List, Dict, Any
import concurrent.futures
import sys

# Add parent directory to path to import the client
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scrapy_client import ScrapyClient, ScrapyAPIError

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Sample list of URLs to scrape
URLS_TO_SCRAPE = [
    "https://quotes.toscrape.com",
    "https://books.toscrape.com",
    "https://example.com",
    "https://news.ycombinator.com",
    "https://httpbin.org",
    "https://python.org",
    "https://github.com",
    "https://wikipedia.org",
    "https://stackoverflow.com",
    "https://reddit.com"
]

def process_results(results: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Process scraping results into a pandas DataFrame.
    
    Args:
        results: List of scraping results
        
    Returns:
        DataFrame with processed results
    """
    processed_data = []
    
    for result in results:
        # Skip failed scrapes
        if result.get('status') != 'success':
            logger.warning(f"Skipping failed scrape: {result.get('url', 'Unknown URL')}")
            continue
        
        # Extract basic info
        url = result.get('url')
        task_id = result.get('task_id')
        
        # Extract page info
        if 'data' in result and 'pages' in result['data']:
            for page in result['data']['pages']:
                page_data = {
                    'url': page.get('url', url),
                    'task_id': task_id,
                    'title': page.get('title', ''),
                    'status_code': page.get('status_code'),
                    'content_type': page.get('content_type', ''),
                    'time': page.get('time')
                }
                
                # Extract word counts if available
                if 'analysis' in page and 'content_analysis' in page['analysis']:
                    analysis = page['analysis']['content_analysis']
                    page_data.update({
                        'word_count': analysis.get('word_count', 0),
                        'sentence_count': analysis.get('sentence_count', 0),
                        'paragraph_count': analysis.get('paragraph_count', 0),
                        'avg_word_length': analysis.get('avg_word_length', 0),
                        'avg_sentence_length': analysis.get('avg_sentence_length', 0),
                        'readability_score': analysis.get('readability_score', 0)
                    })
                
                processed_data.append(page_data)
        else:
            # Handle non-page results like adaptive scraping
            page_data = {
                'url': url,
                'task_id': task_id,
                'status': result.get('status'),
                'time': result.get('time')
            }
            
            # Extract any other data available
            if 'data' in result:
                for key, value in result['data'].items():
                    # Don't include large nested structures
                    if isinstance(value, (str, int, float, bool)):
                        page_data[key] = value
            
            processed_data.append(page_data)
    
    # Convert to DataFrame
    if processed_data:
        return pd.DataFrame(processed_data)
    else:
        return pd.DataFrame()

def scrape_in_batches(client: ScrapyClient, urls: List[str], batch_size: int = 5) -> List[Dict[str, Any]]:
    """
    Scrape URLs in batches to control parallelism.
    
    Args:
        client: ScrapyClient instance
        urls: List of URLs to scrape
        batch_size: Number of URLs to scrape in parallel
        
    Returns:
        List of scraping results
    """
    all_results = []
    
    # Process URLs in batches
    for i in range(0, len(urls), batch_size):
        batch_urls = urls[i:i+batch_size]
        logger.info(f"Processing batch {i//batch_size + 1} with {len(batch_urls)} URLs")
        
        # Extract data from multiple pages in parallel
        batch_results = client.extract_from_multiple_pages(
            urls=batch_urls,
            scrape_type="adaptive",
            parallel=True,
            use_ai=False
        )
        
        all_results.extend(batch_results)
        
        # Don't overwhelm the API
        if i + batch_size < len(urls):
            logger.info("Waiting 5 seconds before next batch...")
            time.sleep(5)
    
    return all_results

def main():
    """Run the parallel scraping example."""
    # Get API key from environment variable
    api_key = os.environ.get('SCRAPY_API_KEY')
    
    if not api_key:
        logger.warning("SCRAPY_API_KEY environment variable not set. Using demo mode.")
        api_key = "demo_key_for_local_development"
    
    # Initialize client
    client = ScrapyClient(
        base_url="http://localhost:8000/api",
        api_key=api_key
    )
    
    try:
        # Start timing
        start_time = time.time()
        
        # Scrape multiple URLs in parallel batches
        logger.info(f"Starting parallel scraping of {len(URLS_TO_SCRAPE)} URLs...")
        results = scrape_in_batches(client, URLS_TO_SCRAPE, batch_size=3)
        
        # Process results