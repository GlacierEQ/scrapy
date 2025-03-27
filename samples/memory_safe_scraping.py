"""
Example demonstrating memory-safe scraping techniques to prevent OOM errors.

This script shows how to use the MemoryManager to handle large scraping jobs
without running out of memory, including chunking operations and offloading data.
"""

import sys
import os
import logging
import time
from typing import List, Dict

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraping_project.memory_manager import MemoryManager, get_memory_manager
from scraping_project.resilient_browser import ResilientBrowser
from selenium.webdriver.common.by import By

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def demo_memory_safe_scraping():
    """Demonstrate memory-safe web scraping techniques."""
    # Initialize memory manager
    memory_manager = MemoryManager(
        warning_threshold=70.0,  # Lower for demonstration purposes
        critical_threshold=85.0,
        monitor_interval=2.0,
        auto_gc=True
    )
    
    # Start memory monitoring
    memory_manager.start_monitoring()
    
    try:
        logger.info("Starting memory-safe scraping demo")
        
        # Show initial memory usage
        usage = memory_manager.get_memory_usage()
        logger.info(f"Initial memory usage: {usage['system_percent']}% "
                   f"({usage['process_rss_mb']:.2f} MB used by process)")
        
        # Create a browser instance
        browser = ResilientBrowser(headless=True, timeout=30)
        browser.start()
        
        # List of URLs to scrape (for demonstration)
        urls = [
            "https://example.com",
            "https://python.org",
            "https://github.com",
            "https://stackoverflow.com",
            "https://developer.mozilla.org"
        ]
        
        # Create a list to store results
        all_results = []
        
        # Process URLs in chunks to manage memory
        for url_batch in memory_manager.chunk_operation(urls, chunk_size=2):
            logger.info(f"Processing batch of {len(url_batch)} URLs")
            
            batch_results = []
            for url in url_batch:
                # Use the memory-safe operation context
                with memory_manager.memory_safe_operation(f"scrape_{url}"):
                    logger.info(f"Scraping {url}")
                    
                    # Navigate to URL
                    browser.get(url)
                    
                    # Extract page title and links
                    try:
                        title = browser.driver.title
                        links = browser.driver.find_elements(By.TAG_NAME, "a")
                        link_data = [{"text": link.text, "href": link.get_attribute("href")} 
                                    for link in links if link.get_attribute("href")]
                        
                        # Extract page text (potentially memory-intensive)
                        page_text = browser.driver.find_element(By.TAG_NAME, "body").text
                        
                        # For large text, we could offload to disk
                        if len(page_text) > 1024 * 10:  # If text is over 10KB
                            logger.info(f"Large text content detected, offloading to disk")
                            text_path = memory_manager.offload_to_disk(
                                page_text, 
                                prefix=f"text_{url.replace('://', '_').replace('/', '_')}"
                            )
                            page_result = {
                                "url": url,
                                "title": title,
                                "links_count": len(link_data),
                                "text_offloaded": True,
                                "text_path": text_path
                            }
                        else:
                            page_result = {
                                "url": url,
                                "title": title, 
                                "links_count": len(link_data),
                                "text": page_text
                            }
                            
                        # For links, if there are many, we might also offload
                        if len(link_data) > 100:
                            links_path = memory_manager.offload_to_disk(
                                link_data,
                                prefix=f"links_{url.replace('://', '_').replace('/', '_')}"
                            )
                            page_result["links_offloaded"] = True
                            page_result["links_path"] = links_path
                        else:
                            page_result["links"] = link_data
                            
                        batch_results.append(page_result)
                        
                    except Exception as e:
                        logger.error(f"Error scraping {url}: {e}")
                        batch_results.append({
                            "url": url,
                            "error": str(e)
                        })
            
            # Check memory after batch
            usage = memory_manager.get_memory_usage()
            logger.info(f"Memory after batch: {usage['system_percent']}% "
                       f"({usage['process_rss_mb']:.2f} MB)")
                       
            # If memory is high, consider offloading batch results
            if usage["system_percent"] > 60:
                logger.info("Memory usage is high, offloading batch results to disk")
                batch_path = memory_manager.offload_to_disk(
                    batch_results,
                    prefix="batch_results"
                )
                # Store path instead of actual results
                all_results.append({"type": "offloaded", "path": batch_path})
            else:
                all_results.extend(batch_results)
        
        # Demonstrate pagination for in-memory results
        paginated = memory_manager.paginate_results(all_results, page_size=2)
        logger.info(f"Pagination: Total {paginated['total']} items, "
                   f"{paginated.get('pages', 1)} pages")
                   
        # Get the first page
        page_1 = memory_manager.get_page(paginated, 1)
        logger.info(f"Page 1 has {len(page_1)} items")
        
        # Show final memory usage
        usage = memory_manager.get_memory_usage()
        logger.info(f"Final memory usage: {usage['system_percent']}% "
                   f"({usage['process_rss_mb']:.2f} MB used by process)")
        
        # Force garbage collection before exiting
        memory_manager.force_garbage_collection()
        
    finally:
        # Stop memory monitoring
        memory_manager.stop_monitoring()
        
        # Close browser
        if 'browser' in locals() and browser:
            browser.close()

if __name__ == "__main__":
    demo_memory_safe_scraping()