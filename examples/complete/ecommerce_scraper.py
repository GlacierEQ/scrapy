"""
E-commerce Product Scraper Example

This example demonstrates how to create a complete e-commerce scraper that extracts
product data from multiple pages, handles pagination, and saves the data in various formats.
It showcases memory optimization, error handling, and data visualization.
"""

import os
import sys
import json
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add parent directory to path for imports
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, "../.."))
sys.path.insert(0, project_root)

# Import Scrapy components
from scraping_project.adaptive_scraper import AdaptiveScraper
from scraping_project.recursive_scraper import RecursiveScraper
from scraping_project.memory_manager import get_memory_manager
from scraping_project.error_handler import ErrorHandler
from scraping_project.resilient_browser import ResilientBrowser
from visualization.data_visualizer import ScrapyVisualizer
from scraping_project.memory_expansion import MemoryOptimizedDataHandler, StreamingProcessor

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(script_dir, "ecommerce_scraper.log"))
    ]
)
logger = logging.getLogger("ecommerce-scraper")

# Initialize error handler
error_handler = ErrorHandler(max_retries=3, retry_delay=2)

# Initialize memory manager
memory_manager = get_memory_manager()
memory_manager.set_warning_threshold(70)
memory_manager.set_critical_threshold(85)

# Define output directory
OUTPUT_DIR = os.path.join(script_dir, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

class EcommerceScraper:
    """
    Comprehensive e-commerce scraper with adaptive extraction
    and memory optimization for large product catalogs.
    """
    
    def __init__(self, base_url: str, max_products: int = 100):
        """
        Initialize the e-commerce scraper.
        
        Args:
            base_url: Base URL of the e-commerce site
            max_products: Maximum number of products to scrape
        """
        self.base_url = base_url
        self.max_products = max_products
        self.output_dir = OUTPUT_DIR
        
        # Initialize components
        self.browser = ResilientBrowser(
            headless=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            timeout=30,
            stealth_mode=True
        )
        self.adaptive_scraper = AdaptiveScraper(
            output_dir=self.output_dir,
            use_ai=False  # Set to True to use AI-powered extraction
        )
        self.recursive_scraper = RecursiveScraper(
            output_dir=self.output_dir,
            config={
                'max_pages': 20,
                'max_depth': 2,
                'stay_on_domain': True,
                'min_request_interval': 1.5,
                'respect_robots_txt': True
            }
        )
        self.data_handler = MemoryOptimizedDataHandler(temp_dir=os.path.join(self.output_dir, "temp"))
        self.products = []
    
    def start(self, category_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Start the scraping process.
        
        Args:
            category_url: Optional URL to a specific category (defaults to base_url)
            
        Returns:
            Dictionary with scraping results
        """
        start_time = time.time()
        target_url = category_url or self.base_url
        
        logger.info(f"Starting e-commerce scraper for {target_url}")
        logger.info(f"Maximum products to extract: {self.max_products}")
        
        try:
            # First, discover product pages using recursive scraper
            logger.info("Phase 1: Discovering product pages...")
            product_urls = self._discover_product_pages(target_url)
            
            logger.info(f"Discovered {len(product_urls)} product pages")
            
            # Second, extract product data using adaptive scraper
            logger.info("Phase 2: Extracting product details...")
            self._extract_products(product_urls)
            
            # Process and clean up the data
            logger.info("Phase 3: Post-processing data...")
            self.products = self._post_process_products(self.products)
            
            # Save the results
            logger.info("Phase 4: Saving results...")
            results = self._save_results()
            
            # Generate visualizations
            logger.info("Phase 5: Generating visualizations...")
            self._generate_visualizations()
            
            # Calculate stats
            duration = time.time() - start_time
            product_count = len(self.products)
            
            logger.info(f"Scraping completed: extracted {product_count} products in {duration:.2f} seconds")
            
            return {
                "status": "success",
                "product_count": product_count,
                "duration_seconds": duration,
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Error during scraping: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "duration_seconds": time.time() - start_time
            }
        finally:
            # Clean up resources
            self._cleanup()
    
    @error_handler.retry_on_error(max_retries=3)
    def _discover_product_pages(self, start_url: str) -> List[str]:
        """
        Discover product pages by crawling the site.
        
        Args:
            start_url: Starting URL for discovery
            
        Returns:
            List of product URLs
        """
        # Configure recursive scraper to look for product pages
        self.recursive_scraper.config.update({
            'follow_url_patterns': [
                "*/product/*",
                "*/item/*",
                "*-p-*"
            ],
            'exclude_url_patterns': [
                "*/cart*",
                "*/checkout*",
                "*/account*",
                "*/login*"
            ]
        })
        
        # Start the crawl
        result = self.recursive_scraper.start_crawl(start_url)
        
        if result.get("status") != "success":
            logger.error("Failed to discover product pages")
            return []
        
        # Extract product URLs from crawl results
        product_urls = []
        
        for page in result.get("data", {}).get("pages", []):
            url = page.get("url", "")
            
            # Check if this looks like a product page
            if any(pattern[1:] in url for pattern in [
                "/product/",
                "/item/",
                "-p-"
            ]):
                product_urls.append(url)
            
            # Check memory usage and yield if needed
            memory_usage = memory_manager.get_memory_usage()
            if memory_usage["process_percent"] > 70:
                memory_manager.reduce_memory_usage()
        
        # Limit to max products
        return product_urls[:self.max_products]
    
    def _extract_products(self, product_urls: List[str]) -> None:
        """
        Extract product data from each URL.
        
        Args:
            product_urls: List of product URLs to scrape
        """
        # Process in batches to control memory usage
        batch_size = 10
        processor = StreamingProcessor()
        
        for i in range(0, len(product_urls), batch_size):
            batch = product_urls[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1} ({len(batch)} products)")
            
            for url in batch:
                try:
                    # Extract product using adaptive scraper
                    result = self.adaptive_scraper.extract_data(
                        url=url,
                        data_type="product"  # Hint that we're looking for product data
                    )
                    
                    if result.get("status") == "success" and "data" in result:
                        # Store the product data
                        product_data = result["data"]
                        
                        # If it's a list, take the first item (should be the main product)
                        if isinstance(product_data, list) and product_data:
                            product_data = product_data[0]
                        
                        # Add source URL if not present
                        if isinstance(product_data, dict):
                            if "url" not in product_data:
                                product_data["url"] = url
                            
                            self.products.append(product_data)
                    else:
                        logger.warning(f"Failed to extract product data from {url}")
                    
                except Exception as e:
                    logger.error(f"Error extracting product from {url}: {str(e)}")
            
            # Force garbage collection after each batch
            memory_manager.reduce_memory_usage()
    
    def _post_process_products(self, products: List[Dict]) -> List[Dict]:
        """
        Clean and normalize product data.
        
        Args:
            products: List of raw product dictionaries
            
        Returns:
            List of processed product dictionaries
        """
        processed_products = []
        
        for product in products:
            # Skip non-dictionary items
            if not isinstance(product, dict):
                continue
                
            # Create a clean product object
            clean_product = {
                "url": product.get("url", ""),
                "title": self._extract_field(product, ["title", "name", "product_name"]),
                "price": self._extract_price(product),
                "currency": self._extract_field(product, ["currency", "currency_code"]),
                "description": self._extract_field(product, ["description", "product_description", "details"]),
                "image_url": self._extract_field(product, ["image", "image_url", "main_image", "primary_image"]),
                "brand": self._extract_field(product, ["brand", "manufacturer", "vendor"]),
                "category": self._extract_field(product, ["category", "categories", "product_type"]),
                "sku": self._extract_field(product, ["sku", "product_id", "item_id"]),
                "availability": self._extract_field(product, ["availability", "in_stock", "stock_status"]),
                "rating": self._extract_rating(product),
                "review_count": self._extract_field(product, ["review_count", "reviews_count", "num_reviews"], default=0)
            }
            
            # Remove None values
            clean_product = {k: v for k, v in clean_product.items() if v is not None}
            
            # Add any additional fields from the original product
            for key, value in product.items():
                if key not in clean_product and key not in ["url", "image", "images"]:
                    clean_product[key] = value
            
            processed_products.append(clean_product)
        
        return processed_products
    
    def _extract_field(self, 
                      product: Dict, 
                      possible_fields: List[str], 
                      default: Any = None) -> Any:
        """Extract a field value from different possible field names."""
        for field in possible_fields:
            if field in product and product[field]:
                return product[field]
        return default
    
    def _extract_price(self, product: Dict) -> Optional[float]:
        """Extract and normalize price value."""
        price = self._extract_field(
            product, 
            ["price", "price_amount", "sale_price", "current_price"]
        )
        
        if price is None:
            return None
            
        # If price is a string, clean and convert to float
        if isinstance(price, str):
            # Remove currency symbols and non-numeric chars except decimal point
            price = ''.join(c for c in price if c.isdigit() or c == '.')
            try:
                return float(price)
            except ValueError:
                return None
                
        # If price is already a number, return it
        if isinstance(price, (int, float)):
            return float(price)
            
        return None
    
    def _extract_rating(self, product: Dict) -> Optional[float]:
        """Extract and normalize rating value."""
        rating = self._extract_field(
            product, 
            ["rating", "average_rating", "product_rating", "stars"]
        )
        
        if rating is None:
            return None
            
        # If rating is a string, convert to float
        if isinstance(rating, str):
            try:
                return float(rating)
            except ValueError:
                return None
        
        # If rating is a number, ensure it's a float
        if isinstance(rating, (int, float)):
            return float(rating)
            
        return None
    
    def _save_results(self) -> Dict[str, str]:
        """
        Save the extracted products in multiple formats.
        
        Returns:
            Dictionary with paths to saved files
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_filename = f"products_{timestamp}"
        
        # Save as JSON
        json_path = os.path.join(self.output_dir, f"{base_filename}.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(self.products, f, indent=2, ensure_ascii=False)
        
        # Save as CSV
        import pandas as pd
        csv_path = os.path.join(self.output_dir, f"{base_filename}.csv")
        
        # Convert to DataFrame and save
        df = pd.DataFrame(self.products)
        df.to_csv(csv_path, index=False, encoding='utf-8')
        
        # Save as Excel
        excel_path = os.path.join(self.output_dir, f"{base_filename}.xlsx")
        df.to_excel(excel_path, index=False)
        
        # Return paths
        return {
            "json": json_path,
            "csv": csv_path,
            "excel": excel_path
        }
    
    def _generate_visualizations(self) -> None:
        """Generate visualizations from the scraped data."""
        if not self.products:
            logger.warning("No products to visualize")
            return
            
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        vis_dir = os.path.join(self.output_dir, "visualizations")
        os.makedirs(vis_dir, exist_ok=True)
        
        # Initialize visualizer
        visualizer = ScrapyVisualizer(output_dir=vis_dir)
        
        # Create a DataFrame from products for easier visualization
        import pandas as pd
        df = pd.DataFrame(self.products)
        
        try:
            # 1. Price distribution
            if 'price' in df.columns:
                import matplotlib.pyplot as plt
                import seaborn as sns
                
                plt.figure(figsize=(10, 6))
                sns.histplot(df['price'].dropna(), kde=True)
                plt.title('Price Distribution')
                plt.xlabel('Price')
                plt.ylabel('Count')
                plt.tight_layout()
                
                price_chart_path = os.path.join(vis_dir, f"price_distribution_{timestamp}.png")
                plt.savefig(price_chart_path)
                plt.close()
                
                logger.info(f"Price distribution chart saved to {price_chart_path}")
            
            # 2. Word cloud from descriptions
            if 'description' in df.columns:
                descriptions = ' '.join(df['description'].dropna().astype(str))
                
                wordcloud_path = os.path.join(vis_dir, f"descriptions_wordcloud_{timestamp}.png")
                
                # Use the visualizer's word cloud function
                visualizer.create_word_cloud(
                    data={"text": descriptions},
                    text_field="text",
                    title="Product Descriptions",
                    save_path=wordcloud_path
                )
                
                logger.info(f"Word cloud saved to {wordcloud_path}")
                
            # 3. Brand distribution
            if 'brand' in df.columns and df['brand'].notna().sum() > 0:
                plt.figure(figsize=(12, 8))
                brand_counts = df['brand'].value_counts().head(15)  # Top 15 brands
                
                sns.barplot(x=brand_counts.values, y=brand_counts.index)
                plt.title('Top Brands')
                plt.xlabel('Count')
                plt.tight_layout()
                
                brands_chart_path = os.path.join(vis_dir, f"brands_{timestamp}.png")
                plt.savefig(brands_chart_path)
                plt.close()
                
                logger.info(f"Brand distribution chart saved to {brands_chart_path}")
                
            # 4. Interactive summary dashboard (if Plotly is available)
            if 'price' in df.columns:
                try:
                    import plotly.express as px
                    import plotly.graph_objects as go
                    from plotly.subplots import make_subplots
                    
                    # Create a dashboard with multiple plots
                    fig = make_subplots(
                        rows=2, cols=2,
                        subplot_titles=("Price Distribution", "Top Brands", 
                                       "Price by Brand", "Rating Distribution")
                    )
                    
                    # 1. Price histogram
                    price_hist = px.histogram(df, x="price")
                    for trace in price_hist.data:
                        fig.add_trace(trace, row=1, col=1)
                    
                    # 2. Brand bar chart
                    if 'brand' in df.columns:
                        brand_counts = df['brand'].value_counts().head(10)
                        fig.add_trace(
                            go.Bar(
                                x=brand_counts.index,
                                y=brand_counts.values
                            ),
                            row=1, col=2
                        )
                    
                    # 3. Price by brand box plot
                    if 'brand' in df.columns:
                        top_brands = df['brand'].value_counts().head(5).index.tolist()
                        brand_df = df[df['brand'].isin(top_brands)]
                        
                        for brand in top_brands:
                            fig.add_trace(
                                go.Box(
                                    y=brand_df[brand_df['brand'] == brand]['price'],
                                    name=brand
                                ),
                                row=2, col=1
                            )
                    
                    # 4. Rating histogram
                    if 'rating' in df.columns:
                        fig.add_trace(
                            go.Histogram(x=df['rating'].dropna()),
                            row=2, col=2
                        )
                    
                    # Update layout
                    fig.update_layout(
                        title_text="Product Analysis Dashboard",
                        height=800,
                        showlegend=False
                    )
                    
                    # Save dashboard
                    dashboard_path = os.path.join(vis_dir, f"dashboard_{timestamp}.html")
                    fig.write_html(dashboard_path)
                    
                    logger.info(f"Interactive dashboard saved to {dashboard_path}")
                    
                except ImportError:
                    logger.warning("Plotly not available, skipping interactive dashboard")
        
        except Exception as e:
            logger.error(f"Error generating visualizations: {str(e)}")
    
    def _cleanup(self) -> None:
        """Clean up resources and temporary files."""
        try:
            # Close browser if open
            if self.browser:
                self.browser.close()
            
            # Clean up temporary files
            self.data_handler.cleanup()
            
            # Force garbage collection
            memory_manager.reduce_memory_usage()
            
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="E-commerce Product Scraper")
    parser.add_argument("url", help="Base URL of the e-commerce site")
    parser.add_argument("--category", help="Specific category URL to scrape")
    parser.add_argument("--max", type=int, default=100, help="Maximum number of products to scrape")
    
    args = parser.parse_args()
    
    # Initialize and run the scraper
    scraper = EcommerceScraper(args.url, max_products=args.max)
    results = scraper.start(args.category)
    
    # Print summary
    if results["status"] == "success":
        print(f"\nScraping completed successfully!")
        print(f"Products extracted: {results['product_count']}")
        print(f"Duration: {results['duration_seconds']:.2f} seconds")
        print("\nResults saved to:")
        for format_type, path in results["results"].items():
            print(f"- {format_type.upper()}: {path}")
    else:
        print(f"\nScraping failed: {results.get('error', 'Unknown error')}")
