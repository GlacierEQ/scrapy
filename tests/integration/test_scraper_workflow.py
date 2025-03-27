"""
Integration tests for the complete scraper workflow.

This test suite verifies that different scraping components work together
correctly, from initial data acquisition to processing and storage.
"""

import os
import unittest
import tempfile
import shutil
import json
from unittest.mock import patch, MagicMock

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scraping_project.general_webscraper import WebpageScraper
from scraping_project.resilient_browser import ResilientBrowser
from scraping_project.adaptive_scraper import AdaptiveScraper
from scraping_project.memory_manager import get_memory_manager
from scraping_project.error_handler import error_context
from scraping_project.db_manager import DatabaseManager

# Sample test HTML
SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Integration Test Page</title>
    <meta name="description" content="A test page for integration tests">
</head>
<body>
    <h1>Welcome to Integration Tests</h1>
    <p>This page is used for testing the scraper workflow.</p>
    
    <div class="content">
        <h2>Main Content</h2>
        <p>Here is some main content for the page.</p>
        <p>This should be extracted and analyzed by the scraper.</p>
    </div>
    
    <div class="sidebar">
        <h3>Related Links</h3>
        <ul>
            <li><a href="/page1">Page 1</a></li>
            <li><a href="/page2">Page 2</a></li>
            <li><a href="/page3">Page 3</a></li>
        </ul>
    </div>
    
    <div class="product-section">
        <div class="product">
            <h3>Product 1</h3>
            <p class="price">$19.99</p>
            <p class="description">This is the first product.</p>
        </div>
        <div class="product">
            <h3>Product 2</h3>
            <p class="price">$29.99</p>
            <p class="description">This is the second product.</p>
        </div>
    </div>
</body>
</html>
"""

class TestScraperWorkflow(unittest.TestCase):
    """Integration tests for scraper workflow."""
    
    def setUp(self):
        """Set up the test environment."""
        # Create temporary directories for output
        self.temp_dir = tempfile.mkdtemp()
        self.output_dir = os.path.join(self.temp_dir, "output")
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Create a mock server HTML file
        self.html_path = os.path.join(self.temp_dir, "test_page.html")
        with open(self.html_path, "w", encoding="utf-8") as f:
            f.write(SAMPLE_HTML)
            
        # Convert to a file URL
        self.test_url = f"file://{self.html_path}"
        
    def tearDown(self):
        """Clean up after tests."""
        # Remove temporary directory
        shutil.rmtree(self.temp_dir)
    
    @patch.object(ResilientBrowser, 'get')
    @patch.object(ResilientBrowser, 'driver')
    def test_general_scraper_workflow(self, mock_driver, mock_get):
        """Test the general scraper workflow."""
        # Mock the browser behavior
        mock_get.return_value = True
        mock_driver.page_source = SAMPLE_HTML
        mock_driver.title = "Integration Test Page"
        mock_driver.find_elements.return_value = []  # No links to follow
        
        # Create the scraper
        scraper = WebpageScraper(output_dir=self.output_dir)
        
        # Mock methods to avoid actual browser interaction
        with patch.object(scraper, '_save_screenshot'), \
             patch.object(scraper, '_save_html'):
            
            # Run the scraper
            result = scraper.save_webpage(
                url=self.test_url,
                follow_links=False,
                compile_text=True
            )
            
            # Assertions
            self.assertEqual(result["status"], "success")
            self.assertIn("data", result)
            self.assertIn("pages", result["data"])
            self.assertEqual(len(result["data"]["pages"]), 1)
            
            # Check page details
            page = result["data"]["pages"][0]
            self.assertEqual(page["title"], "Integration Test Page")
            self.assertEqual(page["url"], self.test_url)
    
    def test_adaptive_scraper_with_product_detection(self):
        """Test the adaptive scraper with product detection."""
        # Create a mock browser and driver
        mock_browser = MagicMock()
        mock_driver = MagicMock()
        mock_browser.driver = mock_driver
        mock_browser.get.return_value = True
        mock_driver.page_source = SAMPLE_HTML
        mock_driver.title = "Integration Test Page"
        
        # Create the scraper
        scraper = AdaptiveScraper(output_dir=self.output_dir)
        scraper.browser = mock_browser
        
        # Test product extraction
        with patch.object(scraper, '_extract_product_data') as mock_extract:
            # Configure mock to return product data
            mock_extract.return_value = {
                'title': 'Product 1',
                'price': '$19.99',
                'description': 'This is the first product.'
            }
            
            # Patch is_product_page to return True
            with patch.object(scraper, '_is_product_page', return_value=True):
                result = scraper._auto_detect_and_extract(
                    BeautifulSoup(SAMPLE_HTML, 'html.parser'), 
                    self.test_url
                )
                
                # Assertions
                mock_extract.assert_called_once()
                self.assertEqual(result['title'], 'Product 1')
                self.assertEqual(result['price'], '$19.99')
    
    def test_error_handling_integration(self):
        """Test error handling integration across components."""
        # Create a mock browser that raises an exception
        mock_browser = MagicMock()
        mock_browser.get.side_effect = WebDriverException("Connection refused")
        
        # Create the scraper
        scraper = WebpageScraper(output_dir=self.output_dir)
        scraper.browser = mock_browser
        
        # Use error_context to handle the expected error
        error_caught = False
        with error_context("test_scrape", reraise=False):
            try:
                result = scraper.save_webpage(url="https://nonexistent.example.com")
            except WebDriverException:
                error_caught = True
        
        # The error should be caught by error_context
        self.assertFalse(error_caught)
    
    def test_memory_management_integration(self):
        """Test memory management integration with scrapers."""
        # Get memory manager
        memory_manager = get_memory_manager()
        
        # Start monitoring
        memory_manager.start_monitoring()
        
        try:
            # Create a large dataset that would benefit from chunking
            large_dataset = [{"index": i, "data": "X" * 10000} for i in range(1000)]
            
            # Process in chunks
            processed_count = 0
            for chunk in memory_manager.chunk_operation(large_dataset, chunk_size=100):
                processed_count += len(chunk)
                
                # Force memory checks between chunks
                usage = memory_manager.get_memory_usage()
                if usage['system_percent'] > 70:
                    # Should trigger garbage collection
                    memory_manager.force_garbage_collection()
            
            # Verify all items were processed
            self.assertEqual(processed_count, 1000)
            
            # Test offloading and retrieving
            with memory_manager.memory_safe_operation("offload_test"):
                # Offload data to disk
                temp_path = memory_manager.offload_to_disk(large_dataset[:100])
                
                # Retrieve it
                retrieved_data = memory_manager.load_from_disk(temp_path)
                
                # Verify data integrity
                self.assertEqual(len(retrieved_data), 100)
                self.assertEqual(retrieved_data[0]['index'], 0)
                self.assertEqual(retrieved_data[99]['index'], 99)
                
                # Clean up
                memory_manager.remove_temp_file(temp_path)
                
        finally:
            # Always stop monitoring
            memory_manager.stop_monitoring()

if __name__ == '__main__':
    unittest.main()
