#!/usr/bin/env python
"""
Simple Demo Application for Scrapy

This is a simple interactive demo that showcases various scraping capabilities.
Run this file to try out different scraping options through a command-line menu.
"""

import os
import sys
import time
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

# Add parent directory to path for imports
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, ".."))
sys.path.insert(0, project_root)

# Try to import scrapy modules
try:
    from scraping_project.general_webscraper import WebpageScraper
    from scraping_project.recursive_scraper import RecursiveScraper
    from scraping_project.adaptive_scraper import AdaptiveScraper
    from scraping_project.memory_manager import get_memory_manager
    from visualization.data_visualizer import ScrapyVisualizer
except ImportError as e:
    print(f"Error importing Scrapy modules: {str(e)}")
    print("Make sure you've installed the required dependencies.")
    print("Try running: pip install -r requirements.txt")
    sys.exit(1)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("scrapy-demo")

# Set up output directory
OUTPUT_DIR = os.path.join(script_dir, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Define demo sites
DEMO_SITES = {
    "quotes": {
        "name": "Quotes to Scrape",
        "url": "http://quotes.toscrape.com/",
        "description": "A website with famous quotes, good for basic scraping examples."
    },
    "books": {
        "name": "Books to Scrape",
        "url": "http://books.toscrape.com/",
        "description": "A fictional bookstore with multiple categories and pages."
    },
    "news": {
        "name": "HackerNews",
        "url": "https://news.ycombinator.com/",
        "description": "Technology news aggregator, good for extracting links and headlines."
    },
    "ecommerce": {
        "name": "Demo E-commerce",
        "url": "https://webscraper.io/test-sites/e-commerce/allinone",
        "description": "E-commerce demo site with product listings."
    },
    "wikipedia": {
        "name": "Wikipedia - Web Scraping",
        "url": "https://en.wikipedia.org/wiki/Web_scraping",
        "description": "Wikipedia article about web scraping, good for content extraction."
    }
}

class ScrapyDemo:
    """Interactive demo for Scrapy features."""
    
    def __init__(self):
        """Initialize the demo application."""
        self.output_dir = OUTPUT_DIR
        self.last_result = None
        self.last_result_path = None
        
        # Initialize memory manager
        self.memory_manager = get_memory_manager()
        self.memory_manager.set_warning_threshold(70)
        
        print("\n" + "="*60)
        print("Scrapy: Advanced Web Scraping Toolkit - Interactive Demo")
        print("="*60)
        print("This demo lets you try out different scraping capabilities.\n")
    
    def show_main_menu(self) -> None:
        """Display the main menu and handle user input."""
        while True:
            print("\n" + "-"*60)
            print("MAIN MENU")
            print("-"*60)
            print("1. Simple webpage scraping")
            print("2. Recursive website crawling")
            print("3. Adaptive content extraction")
            print("4. Visualization tools")
            print("5. Memory-optimized scraping")
            print("6. View available demo sites")
            print("7. Exit")
            
            choice = input("\nEnter your choice (1-7): ").strip()
            
            if choice == '1':
                self.simple_scraping_demo()
            elif choice == '2':
                self.recursive_scraping_demo()
            elif choice == '3':
                self.adaptive_scraping_demo()
            elif choice == '4':
                self.visualization_demo()
            elif choice == '5':
                self.memory_optimized_demo()
            elif choice == '6':
                self.show_demo_sites()
            elif choice == '7':
                print("\nThank you for trying Scrapy! Goodbye!")
                sys.exit(0)
            else:
                print("\nInvalid choice. Please enter a number between 1 and 7.")
    
    def get_url_input(self, default_site: str = "quotes") -> str:
        """Get URL input from user or use a demo site."""
        print("\nYou can enter a URL or use one of our demo sites.")
        print("For demo sites, enter the shortcode (e.g. 'quotes' for Quotes to Scrape)")
        print("To see available demo sites, enter 'list'")
        
        url_input = input(f"\nEnter URL or shortcode [default: {default_site}]: ").strip()
        
        if not url_input:
            url_input = default_site
            
        if url_input.lower() == 'list':
            self.show_demo_sites()
            return self.get_url_input(default_site)
        
        # Check if input is a demo site shortcode
        if url_input.lower() in DEMO_SITES:
            demo = DEMO_SITES[url_input.lower()]
            print(f"\nUsing demo site: {demo['name']}")
            return demo["url"]
        
        # Validate URL format
        if not (url_input.startswith('http://') or url_input.startswith('https://')):
            print("\nAdding https:// prefix to URL...")
            url_input = 'https://' + url_input
        
        return url_input
    
    def generate_output_path(self, prefix: str, ext: str = 'json') -> str:
        """Generate a timestamped output file path."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return os.path.join(self.output_dir, f"{prefix}_{timestamp}.{ext}")
    
    def simple_scraping_demo(self) -> None:
        """Demo for simple webpage scraping."""
        print("\n" + "-"*60)
        print("SIMPLE WEBPAGE SCRAPING")
        print("-"*60)
        print("This demo will scrape a single webpage and extract its content.")
        
        # Get URL
        url = self.get_url_input()
        
        # Options
        get_screenshot = self._get_yes_no_input("Save screenshot?", True)
        get_text = self._get_yes_no_input("Analyze text content?", True)
        get_html = self._get_yes_no_input("Save HTML?", True)
        
        print("\nStarting simple scrape...")
        
        try:
            # Initialize scraper
            scraper = WebpageScraper(output_dir=self.output_dir)
            
            # Start timer
            start_time = time.time()
            
            # Perform scrape
            result = scraper.save_webpage(
                url=url,
                follow_links=False,
                compile_text=get_text,
                save_screenshot=get_screenshot,
                save_html=get_html
            )
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Save result
            output_path = self.generate_output_path("simple_scrape")
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            
            self.last_result = result
            self.last_result_path = output_path
            
            # Show summary
            self._show_scrape_summary(result, duration, output_path)
            
            # Offer to create visualizations
            if get_text and self._get_yes_no_input("\nCreate a word cloud from text?", False):
                self._create_word_cloud(result)

        except Exception as e:
            logger.error(f"Error during scraping: {str(e)}")
            print(f"\n❌ Error: {str(e)}")
            print("Please check the URL and try again.")
    
    def recursive_scraping_demo(self) -> None:
        """Demo for recursive website crawling."""
        print("\n" + "-"*60)
        print("RECURSIVE WEBSITE CRAWLING")
        print("-"*60)
        print("This demo will crawl a website by following links starting from a URL.")
        
        # Get URL
        url = self.get_url_input("books")
        
        # Options
        max_depth = self._get_int_input("Maximum crawl depth", 2, 1, 5)
        max_pages = self._get_int_input("Maximum pages to scrape", 20, 1, 100)
        stay_on_domain = self._get_yes_no_input("Stay on the same domain?", True)
        
        print(f"\nStarting recursive crawl with depth={max_depth}, max_pages={max_pages}...")
        
        try:
            # Initialize scraper with configuration
            scraper = RecursiveScraper(
                output_dir=self.output_dir,
                config={
                    'max_depth': max_depth,
                    'max_pages': max_pages,
                    'stay_on_domain': stay_on_domain,
                    'min_request_interval': 1.0
                }
            )
            
            # Start timer
            start_time = time.time()
            
            # Perform crawl
            result = scraper.start_crawl(url)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Save result
            output_path = self.generate_output_path("recursive_scrape")
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            
            self.last_result = result
            self.last_result_path = output_path
            
            # Show summary
            page_count = len(result.get('data', {}).get('pages', []))
            print(f"\n✅ Recursive scraping complete!")
            print(f"Scraped {page_count} pages in {duration:.2f} seconds")
            print(f"Results saved to: {output_path}")
            
            # Get discovered links
            pages = result.get('data', {}).get('pages', [])
            print(f"\nDiscovered pages: {len(pages)}")
            if pages and len(pages) > 0:
                print("\nSample of discovered pages:")
                for page in pages[:min(5, len(pages))]:
                    title = page.get('title', 'No title')
                    url = page.get('url', 'No URL')
                    print(f"- {title} ({url})")
                
                if len(pages) > 5:
                    print(f"... and {len(pages) - 5} more")
            
            # Offer to create site map visualization
            if self._get_yes_no_input("\nCreate a site map visualization?", False):
                self._create_site_map(result)
                
        except Exception as e:
            logger.error(f"Error during recursive scraping: {str(e)}")
            print(f"\n❌ Error: {str(e)}")
            print("Please check the URL and try again.")
    
    def adaptive_scraping_demo(self) -> None:
        """Demo for adaptive content extraction."""
        print("\n" + "-"*60)
        print("ADAPTIVE CONTENT EXTRACTION")
        print("-"*60)
        print("This demo will automatically detect and extract structured content.")
        print("It works best with pages containing lists, products, articles, etc.")
        
        # Get URL
        url = self.get_url_input("ecommerce")
        
        # Options
        content_types = ["auto", "article", "product", "list", "table"]
        print("\nContent type to extract:")
        for i, ctype in enumerate(content_types, 1):
            print(f"{i}. {ctype}")
        
        type_choice = self._get_int_input("Select content type", 1, 1, len(content_types))
        content_type = content_types[type_choice - 1]
        
        use_ai = self._get_yes_no_input("Use AI for better extraction? (slower)", False)
        
        print(f"\nStarting adaptive scrape with type={content_type}, use_ai={use_ai}...")
        
        try:
            # Initialize scraper
            scraper = AdaptiveScraper(
                output_dir=self.output_dir,
                use_ai=use_ai
            )
            
            # Start timer
            start_time = time.time()
            
            # Perform extraction
            result = scraper.extract_data(
                url=url,
                data_type=content_type,
                save_screenshot=True
            )
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Save result
            output_path = self.generate_output_path("adaptive_scrape")
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            
            self.last_result = result
            self.last_result_path = output_path
            
            # Show summary
            print(f"\n✅ Adaptive scraping complete in {duration:.2f} seconds!")
            
            # Display extracted data summary
            data = result.get('data', [])
            if isinstance(data, list):
                print(f"Extracted {len(data)} items")
                if data:
                    print("\nSample of extracted data:")
                    self._show_sample_items(data)
            else:
                print("\nExtracted data:")
                print(json.dumps(data, indent=2)[:500] + "...")
            
            print(f"\nFull results saved to: {output_path}")
            
            # Offer to create content dashboard
            if self._get_yes_no_input("\nCreate a content analysis dashboard?", False):
                self._create_content_dashboard(result)
                
        except Exception as e:
            logger.error(f"Error during adaptive scraping: {str(e)}")
            print(f"\n❌ Error: {str(e)}")
            print("Please check the URL and try again.")
    
    def visualization_demo(self) -> None:
        """Demo for visualization capabilities."""
        print("\n" + "-"*60)
        print("VISUALIZATION TOOLS")
        print("-"*60)
        print("This demo will showcase visualization capabilities.")
        
        # Check if we have previous results to visualize
        if not self.last_result or not self.last_result_path:
            print("\nNo previous scraping results found.")
            print("Run a scraping demo first or load a result file.")
            
            load_file = self._get_yes_no_input("Load a result file?", True)
            if load_file:
                file_path = input("\nEnter the path to a JSON result file: ").strip()
                if os.path.exists(file_path) and file_path.lower().endswith('.json'):
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            self.last_result = json.load(f)
                            self.last_result_path = file_path
                        print(f"\nLoaded result file: {file_path}")
                    except Exception as e:
                        print(f"\nError loading file: {str(e)}")
                        return
                else:
                    print("\nInvalid file path or not a JSON file.")
                    return
            else:
                return
        
        # Show visualization options
        print("\nVisualization options:")
        print("1. Word cloud (from text content)")
        print("2. Site map (from recursive scrape)")
        print("3. Content analysis dashboard")
        print("4. Back to main menu")
        
        choice = input("\nEnter your choice (1-4): ").strip()
        
        if choice == '1':
            self._create_word_cloud(self.last_result)
        elif choice == '2':
            self._create_site_map(self.last_result)
        elif choice == '3':
            self._create_content_dashboard(self.last_result)
        elif choice == '4':
            return
        else:
            print("Invalid choice.")
    
    def memory_optimized_demo(self) -> None:
        """Demo for memory-optimized scraping."""
        print("\n" + "-"*60)
        print("MEMORY-OPTIMIZED SCRAPING")
        print("-"*60)
        print("This demo shows how Scrapy handles large datasets efficiently.")
        
        # Get URL
        url = self.get_url_input("books")
        
        # Show current memory usage
        mem_usage = self.memory_manager.get_memory_usage()
        print(f"\nCurrent memory usage:")
        print(f"- Process memory: {mem_usage['process_rss_mb']:.1f} MB")
        print(f"- System memory: {mem_usage['system_percent']:.1f}%")
        
        # Options
        print("\nIn memory-optimized mode, Scrapy will:")
        print("- Process data in chunks instead of loading everything at once")
        print("- Periodically free up unused memory")
        print("- Use streaming for large files")
        print("- Monitor memory usage and adapt accordingly")
        
        chunk_size = self._get_int_input("Processing chunk size (pages)", 5, 1, 50)
        max_pages = self._get_int_input("Maximum pages to scrape", 50, 10, 500)
        
        print(f"\nStarting memory-optimized scrape with max_pages={max_pages}...")
        
        try:
            # Import memory optimization components
            from scraping_project.memory_expansion import StreamingProcessor
            
            # Initialize scraper with memory optimization settings
            scraper = RecursiveScraper(
                output_dir=self.output_dir,
                config={
                    'max_pages': max_pages,
                    'stay_on_domain': True,
                    'optimize_memory': True,  # Enable memory optimization
                    'min_request_interval': 1.0
                }
            )
            
            # Start timer
            start_time = time.time()
            
            # Show progress indicator
            print("\nScraping in progress...")
            
            # Track memory usage during scraping
            max_mem_usage = 0
            start_mem = self.memory_manager.get_memory_usage()['process_rss_mb']
            
            # Perform crawl with chunked processing
            result = {'status': 'pending', 'data': {'pages': []}}
            pages_processed = 0
            
            # Process in batches
            for i in range(0, max_pages, chunk_size):
                batch_max = min(i + chunk_size, max_pages)
                print(f"\nProcessing batch {i//chunk_size + 1} (pages {i+1}-{batch_max})...")
                
                # Configure batch limits
                scraper.config['max_pages'] = chunk_size
                
                # If this is not the first batch, we need to avoid 
                # re-crawling pages we've already seen
                if i > 0 and 'data' in result and 'pages' in result['data']:
                    # Extract already visited URLs to avoid duplicates
                    visited_urls = [page.get('url') for page in result['data']['pages']]
                    scraper.visited_urls = set(visited_urls)
                
                # Perform batch crawl
                if i == 0:
                    batch_result = scraper.start_crawl(url)
                else:
                    # For subsequent batches, we'll continue from the last batch
                    # using discovered but unvisited links
                    next_urls = []
                    for page in result['data']['pages']:
                        if 'links' in page:
                            for link in page['links']:
                                if 'href' in link and link['href'] not in scraper.visited_urls:
                                    next_urls.append(link['href'])
                    
                    if not next_urls:
                        print("No more links to crawl.")
                        break
                        
                    # Start from a new URL for this batch
                    batch_result = scraper.start_crawl(next_urls[0])
                
                # Combine results
                if i == 0:
                    result = batch_result
                else:
                    if 'data' in batch_result and 'pages' in batch_result['data']:
                        result['data']['pages'].extend(batch_result['data']['pages'])
                
                # Update progress
                pages_processed = len(result['data']['pages'])
                print(f"Total pages scraped: {pages_processed}")
                
                # Check and report memory usage
                mem_usage = self.memory_manager.get_memory_usage()
                max_mem_usage = max(max_mem_usage, mem_usage['process_rss_mb'])
                print(f"Current memory usage: {mem_usage['process_rss_mb']:.1f} MB")
                
                # Force memory cleanup
                if i < max_pages - chunk_size:  # Don't clean up after the last batch
                    print("Cleaning up memory...")
                    self.memory_manager.reduce_memory_usage()
                    after_cleanup = self.memory_manager.get_memory_usage()['process_rss_mb']
                    print(f"Memory after cleanup: {after_cleanup:.1f} MB")
                
                # Pause between batches
                if i < max_pages - chunk_size:  # Don't pause after the last batch
                    print("Pausing between batches...")
                    time.sleep(2)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Save result with streaming
            output_path = self.generate_output_path("memory_optimized_scrape")
            print("\nSaving results using streaming to avoid memory spikes...")
            
            processor = StreamingProcessor()
            processor.save_large_json(result, output_path)
            
            self.last_result = result
            self.last_result_path = output_path
            
            # Show summary
            print(f"\n✅ Memory-optimized scraping complete!")
            print(f"Scraped {pages_processed} pages in {duration:.2f} seconds")
            print(f"Maximum memory usage: {max_mem_usage:.1f} MB (delta: {max_mem_usage - start_mem:.1f} MB)")
            print(f"Current memory usage: {self.memory_manager.get_memory_usage()['process_rss_mb']:.1f} MB")
            print(f"Results saved to: {output_path}")
            
            # Provide memory usage summary
            print("\nMemory Optimization Summary:")
            print(f"- Start memory usage: {start_mem:.1f} MB")
            print(f"- Max memory usage: {max_mem_usage:.1f} MB")
            print(f"- Current memory usage: {self.memory_manager.get_memory_usage()['process_rss_mb']:.1f} MB")
            print(f"- Memory efficiency: {pages_processed / (max_mem_usage - start_mem):.2f} pages/MB")
            
        except Exception as e:
            logger.error(f"Error during memory-optimized scraping: {str(e)}")
            print(f"\n❌ Error: {str(e)}")
            print("Please check the URL and try again.")
    
    def show_demo_sites(self) -> None:
        """Display available demo sites."""
        print("\n" + "-"*60)
        print("AVAILABLE DEMO SITES")
        print("-"*60)
        
        for code, site in DEMO_SITES.items():
            print(f"\n[{code}] {site['name']}")
            print(f"URL: {site['url']}")
            print(f"Description: {site['description']}")
        
        print("\nUse these shortcodes when prompted for a URL in the demos.")
        input("\nPress Enter to continue...")
    
    def _get_yes_no_input(self, prompt: str, default: bool = True) -> bool:
        """Get a yes/no input from the user."""
        default_text = "Y/n" if default else "y/N"
        response = input(f"{prompt} [{default_text}]: ").strip().lower()
        
        if not response:
            return default
            
        return response.startswith('y')
    
    def _get_int_input(self, prompt: str, default: int, min_val: int, max_val: int) -> int:
        """Get an integer input from the user within a range."""
        while True:
            try:
                response = input(f"{prompt} [{default}]: ").strip()
                
                if not response:
                    return default
                    
                value = int(response)
                
                if min_val <= value <= max_val:
                    return value
                else:
                    print(f"Please enter a value between {min_val} and {max_val}.")
            except ValueError:
                print("Please enter a valid number.")
    
    def _show_sample_items(self, items: List[Dict], max_items: int = 3) -> None:
        """Show a sample of extracted items."""
        for i, item in enumerate(items[:max_items]):
            print(f"\nItem {i+1}:")
            # Get the first few key-value pairs
            sample_data = dict(list(item.items())[:5])
            print(json.dumps(sample_data, indent=2))
            
        if len(items) > max_items:
            print(f"\n... and {len(items) - max_items} more items")
    
    def _show_scrape_summary(self, result: Dict[str, Any], duration: float, output_path: str) -> None:
        """Show a summary of scraping results."""
        if result.get('status') == 'success':
            print(f"\n✅ Scraping completed successfully in {duration:.2f} seconds!")
            
            # Extract page info
            page = result.get('data', {}).get('pages', [{}])[0]
            
            # Show page details
            print("\nPage details:")
            print(f"- Title: {page.get('title', 'N/A')}")
            print(f"- URL: {page.get('url', 'N/A')}")
            
            # Show content analysis if available
            if 'analysis' in page and 'content_analysis' in page['analysis']:
                analysis = page['analysis']['content_analysis']
                print("\nContent analysis:")
                print(f"- Word count: {analysis.get('word_count', 'N/A')}")
                print(f"- Sentences: {analysis.get('sentence_count', 'N/A')}")
                print(f"- Paragraphs: {analysis.get('paragraph_count', 'N/A')}")
                print(f"- Readability score: {analysis.get('readability_score', 'N/A')}")
            
            # Show link count if available
            if 'links' in page:
                print(f"\nExtracted {len(page['links'])} links")
            
            print(f"\nResults saved to: {output_path}")
        else:
            print(f"\n❌ Scraping failed: {result.get('error', 'Unknown error')}")
    
    def _create_word_cloud(self, result: Dict[str, Any]) -> None:
        """Create a word cloud from scraped text."""
        # Extract text from result
        text = ""
        
        # Handle different result structures
        if 'data' in result and 'pages' in result['data']:
            for page in result['data']['pages']:
                if 'text' in page:
                    text += page['text'] + " "
                if 'content' in page:
                    text += page['content'] + " "
        elif 'data' in result and isinstance(result['data'], list):
            # For adaptive scraper results with multiple items
            for item in result['data']:
                if isinstance(item, dict):
                    for k, v in item.items():
                        if isinstance(v, str) and len(v) > 100:
                            text += v + " "
        elif 'data' in result and isinstance(result['data'], dict):
            # For adaptive scraper results with single item
            for k, v in result['data'].items():
                if isinstance(v, str) and len(v) > 100:
                    text += v + " "
        
        if not text:
            print("\n❌ No suitable text found for word cloud.")
            return
        
        try:
            # Initialize visualizer
            visualizer = ScrapyVisualizer(output_dir=self.output_dir)
            
            # Generate word cloud
            output_path = self.generate_output_path("wordcloud", "png")
            
            print("\nGenerating word cloud...")
            visualizer.create_word_cloud(
                data={"text": text},
                text_field="text",
                title="Word Cloud from Scraped Content",
                save_path=output_path
            )
            
            print(f"\n✅ Word cloud saved to: {output_path}")
            print("Open this file to view the visualization.")
            
        except Exception as e:
            logger.error(f"Error creating word cloud: {str(e)}")
            print(f"\n❌ Error creating word cloud: {str(e)}")
    
    def _create_site_map(self, result: Dict[str, Any]) -> None:
        """Create a site map visualization from scraped data."""
        if 'data' not in result or 'pages' not in result['data'] or len(result['data']['pages']) < 2:
            print("\n❌ Not enough pages for site map visualization.")
            print("Site maps require results from recursive scraping with multiple pages.")
            return
        
        try:
            # Initialize visualizer
            visualizer = ScrapyVisualizer(output_dir=self.output_dir)
            
            # Choose visualization type
            interactive = self._get_yes_no_input("Create interactive visualization?", True)
            
            # Generate site map
            if interactive:
                output_path = self.generate_output_path("sitemap", "html")
                print("\nGenerating interactive site map...")
                visualizer.create_interactive_site_map(
                    data=result,
                    title="Interactive Site Map",
                    save_path=output_path
                )
            else:
                output_path = self.generate_output_path("sitemap", "png")
                print("\nGenerating site map visualization...")
                visualizer.create_site_map(
                    data=result,
                    title="Site Map",
                    save_path=output_path
                )
            
            print(f"\n✅ Site map saved to: {output_path}")
            print("Open this file to view the visualization.")
            
        except Exception as e:
            logger.error(f"Error creating site map: {str(e)}")
            print(f"\n❌ Error creating site map: {str(e)}")
    
    def _create_content_dashboard(self, result: Dict[str, Any]) -> None: