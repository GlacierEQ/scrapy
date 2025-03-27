#!/usr/bin/env python
"""
E-commerce Scraper Runner

A command-line utility to run the e-commerce scraper with various configurations.
"""

import os
import sys
import json
import argparse
import logging
import time
from datetime import datetime

# Add parent directory to path for imports
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, "../.."))
sys.path.insert(0, project_root)

# Import the scraper
from ecommerce_scraper import EcommerceScraper

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(script_dir, "scraper_run.log"))
    ]
)
logger = logging.getLogger("scraper-runner")

def load_config():
    """Load configuration from the config file."""
    config_path = os.path.join(script_dir, "config.json")
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return {}

def get_demo_site(name):
    """Get a demo site configuration by name."""
    config = load_config()
    
    for site in config.get('demo_sites', []):
        if site['name'].lower() == name.lower():
            return site
    
    return None

def list_demo_sites():
    """List available demo sites."""
    config = load_config()
    sites = config.get('demo_sites', [])
    
    if not sites:
        print("No demo sites configured.")
        return
    
    print("\nAvailable Demo Sites:")
    print("=====================")
    
    for i, site in enumerate(sites, 1):
        print(f"{i}. {site['name']}")
        print(f"   URL: {site['url']}")
        print(f"   Category: {site.get('category', 'N/A')}")
        print(f"   Max Products: {site.get('max_products', 100)}")
        print()

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run the E-commerce Scraper")
    
    # Main arguments
    parser.add_argument("--url", help="Base URL of the e-commerce site")
    parser.add_argument("--category", help="Specific category URL to scrape")
    parser.add_argument("--max", type=int, help="Maximum number of products to scrape")
    parser.add_argument("--output", help="Output directory for results")
    
    # Demo mode options
    parser.add_argument("--demo", help="Use a predefined demo site (use --list to see options)")
    parser.add_argument("--list", action="store_true", help="List available demo sites")
    
    # Additional options
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--save-memory", action="store_true", help="Optimize for memory usage")
    
    args = parser.parse_args()
    
    # Set debug logging if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # List demo sites if requested
    if args.list:
        list_demo_sites()
        return 0
    
    # Get configuration
    config = load_config()
    
    # If demo mode, get demo site configuration
    if args.demo:
        demo_config = get_demo_site(args.demo)
        
        if not demo_config:
            logger.error(f"Demo site '{args.demo}' not found. Use --list to see available options.")
            return 1
        
        logger.info(f"Using demo site: {demo_config['name']}")
        
        # Set parameters from demo config if not explicitly provided
        if not args.url:
            args.url = demo_config['url']
        
        if not args.category and 'category' in demo_config:
            args.category = demo_config['category']
            
        if not args.max and 'max_products' in demo_config:
            args.max = demo_config['max_products']
    
    # Check required parameters
    if not args.url:
        logger.error("URL is required. Use --url or --demo to specify a target.")
        parser.print_help()
        return 1
    
    # Set defaults from config if not specified in arguments
    if not args.max:
        args.max = 100  # Default to 100 products
    
    # Create output directory with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = args.output or os.path.join(script_dir, "output", f"run_{timestamp}")
    os.makedirs(output_dir, exist_ok=True)
    
    # Initialize and run the scraper
    try:
        logger.info(f"Starting scraper for {args.url}")
        logger.info(f"Output directory: {output_dir}")
        
        # Track execution time
        start_time = time.time()
        
        # Initialize scraper with configuration
        scraper = EcommerceScraper(
            base_url=args.url,
            max_products=args.max
        )
        
        # Override output directory
        scraper.output_dir = output_dir
        
        # Apply memory optimization if requested
        if args.save_memory:
            logger.info("Memory optimization enabled")
            # Lower thresholds to be more aggressive with memory cleanup
            from scraping_project.memory_manager import get_memory_manager
            memory_manager = get_memory_manager()
            memory_manager.set_warning_threshold(60)
            memory_manager.set_critical_threshold(75)
        
        # Start the scraper
        results = scraper.start(args.category)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Print summary
        if results["status"] == "success":
            print(f"\nScraping completed successfully!")
            print(f"Products extracted: {results['product_count']}")
            print(f"Duration: {duration:.2f} seconds")
            print(f"Speed: {results['product_count'] / duration:.2f} products/second")
            print("\nResults saved to:")
            for format_type, path in results["results"].items():
                print(f"- {format_type.upper()}: {os.path.basename(path)}")
            print(f"\nOutput directory: {output_dir}")
            
            return 0
        else:
            print(f"\nScraping failed: {results.get('error', 'Unknown error')}")
            print(f"Duration: {duration:.2f} seconds")
            
            return 1
        
    except KeyboardInterrupt:
        logger.info("Scraping interrupted by user")
        print("\nScraping interrupted. Cleaning up...")
        return 130  # Standard exit code for SIGINT
        
    except Exception as e:
        