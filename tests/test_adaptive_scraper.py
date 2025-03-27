"""
Unit tests for the adaptive scraper module.

This test suite validates the automatic data extraction capabilities,
pattern recognition, and learning features of the adaptive scraper.
"""

import os
import unittest
import tempfile
import json
from unittest.mock import patch, MagicMock
from bs4 import BeautifulSoup

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraping_project.adaptive_scraper import AdaptiveScraper

class TestAdaptiveScraper(unittest.TestCase):
    """Test case for AdaptiveScraper class."""
    
    def setUp(self):
        """Set up test environment before each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.scraper = AdaptiveScraper(output_dir=self.temp_dir, use_ai=False)
        
        # Sample HTML content for testing
        self.product_html = """
        <html>
            <head><title>Test Product</title></head>
            <body>
                <h1 class="product-title">Premium Headphones</h1>
                <div class="price">$199.99</div>
                <div class="product-description">
                    High-quality wireless headphones with noise cancellation.
                </div>
                <div class="product-image">
                    <img src="headphones.jpg" alt="Premium Headphones">
                </div>
                <div class="specifications">
                    <dl>
                        <dt>Battery Life</dt>
                        <dd>20 hours</dd>
                        <dt>Connectivity</dt>
                        <dd>Bluetooth 5.0</dd>
                    </dl>
                </div>
            </body>
        </html>
        """
        
        self.list_html = """
        <html>
            <head><title>Product List</title></head>
            <body>
                <h1>Latest Products</h1>
                <ul class="product-list">
                    <li>
                        <h2>Smartphone</h2>
                        <p>Latest model with 5G</p>
                        <a href="/product/1">View details</a>
                    </li>
                    <li>
                        <h2>Laptop</h2>
                        <p>Powerful processor and graphics</p>
                        <a href="/product/2">View details</a>
                    </li>
                    <li>
                        <h2>Tablet</h2>
                        <p>Lightweight with great display</p>
                        <a href="/product/3">View details</a>
                    </li>
                </ul>
            </body>
        </html>
        """
        
        self.article_html = """
        <html>
            <head><title>Tech News</title></head>
            <body>
                <article>
                    <h1>The Future of AI</h1>
                    <div class="author">By Jane Smith</div>
                    <div class="date">2023-05-10</div>
                    <div class="content">
                        <p>Artificial intelligence has made significant progress.</p>
                        <p>New models show unprecedented capabilities.</p>
                        <h2>Key Developments</h2>
                        <p>Several breakthroughs have been achieved.</p>
                    </div>
                </article>
            </body>
        </html>
        """
    
    def tearDown(self):
        """Clean up after each test."""
        # Clean up temporary files
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('scraping_project.adaptive_scraper.ResilientBrowser')
    def test_extract_product_data(self, mock_browser):
        """Test product data extraction."""
        # Setup browser mock
        mock_instance = mock_browser.return_value
        mock_instance.driver.page_source = self.product_html
        mock_instance.get.return_value = True
        
        # Test extraction
        soup = BeautifulSoup(self.product_html, 'html.parser')
        product_data = self.scraper._extract_product_data(soup, None)
        
        # Assertions
        self.assertEqual(product_data['title'], 'Premium Headphones')
        self.assertEqual(product_data['price'], '$199.99')
        self.assertTrue('description' in product_data)
        self.assertTrue('specifications' in product_data)
        self.assertEqual(product_data['specifications']['Battery Life'], '20 hours')
        self.assertEqual(product_data['specifications']['Connectivity'], 'Bluetooth 5.0')

    @patch('scraping_project.adaptive_scraper.ResilientBrowser')
    def test_extract_list_items(self, mock_browser):
        """Test list items extraction."""
        # Setup browser mock
        mock_instance = mock_browser.return_value
        mock_instance.driver.page_source = self.list_html
        mock_instance.get.return_value = True
        
        # Test extraction
        soup = BeautifulSoup(self.list_html, 'html.parser')
        list_items = self.scraper._extract_list_items(soup, None)
        
        # Assertions
        self.assertEqual(len(list_items), 3)
        self.assertEqual(list_items[0]['title'], 'Smartphone')
        self.assertEqual(list_items[1]['title'], 'Laptop')
        self.assertEqual(list_items[2]['title'], 'Tablet')
        self.assertEqual(list_items[0]['text'], 'Latest model with 5G')
        self.assertEqual(list_items[0]['links'][0]['href'], '/product/1')

    @patch('scraping_project.adaptive_scraper.ResilientBrowser')
    def test_extract_article_content(self, mock_browser):
        """Test article content extraction."""
        # Setup browser mock
        mock_instance = mock_browser.return_value
        mock_instance.driver.page_source = self.article_html
        mock_instance.get.return_value = True
        
        # Test extraction
        soup = BeautifulSoup(self.article_html, 'html.parser')
        article_data = self.scraper._extract_article_content(soup, None)
        
        # Assertions
        self.assertEqual(article_data['title'], 'The Future of AI')
        self.assertEqual(article_data['author'], 'By Jane Smith')
        self.assertEqual(article_data['date'], '2023-05-10')
        self.assertEqual(len(article_data['content']), 3)
        self.assertEqual(article_data['content'][0], 'Artificial intelligence has made significant progress.')
        self.assertTrue('subheadings' in article_data)
        self.assertEqual(article_data['subheadings'][0], 'Key Developments')

    @patch('scraping_project.adaptive_scraper.ResilientBrowser')
    def test_is_product_page(self, mock_browser):
        """Test product page detection."""
        soup = BeautifulSoup(self.product_html, 'html.parser')
        is_product = self.scraper._is_product_page(soup)
        self.assertTrue(is_product)

    @patch('scraping_project.adaptive_scraper.ResilientBrowser')
    def test_is_article_page(self, mock_browser):
        """Test article page detection."""
        soup = BeautifulSoup(self.article_html, 'html.parser')
        is_article = self.scraper._is_article_page(soup)
        self.assertTrue(is_article)

    @patch('scraping_project.adaptive_scraper.ResilientBrowser')
    def test_is_listing_page(self, mock_browser):
        """Test listing page detection."""
        soup = BeautifulSoup(self.list_html, 'html.parser')
        is_listing = self.scraper._is_listing_page(soup)
        self.assertTrue(is_listing)

    @patch('scraping_project.adaptive_scraper.ResilientBrowser')
    def test_learn_from_example(self, mock_browser):
        """Test learning extraction patterns from examples."""
        # Setup browser mock
        mock_instance = mock_browser.return_value
        mock_instance.driver.page_source = self.product_html
        mock_instance.get.return_value = True
        
        # Example product data
        example_data = {
            "title": "Premium Headphones",
            "price": "$199.99",
            "description": "High-quality wireless headphones with noise cancellation."
        }
        
        # Mock the _discover_patterns method to return a pattern
        with patch.object(self.scraper, '_discover_patterns') as mock_discover:
            mock_discover.return_value = [{
                'field': 'title',
                'selector': 'h1.product-title',
                'attribute': 'text',
                'manipulation': None
            }]
            
            # Test learning
            result = self.scraper.learn_from_example("https://example.com/product", example_data)
            
            # Assertions
            self.assertEqual(result['status'], 'success')
            self.assertTrue('pattern_id' in result)
            self.assertEqual(result['pattern_count'], 1)

    @patch('scraping_project.adaptive_scraper.ResilientBrowser')
    def test_extract_similar(self, mock_browser):
        """Test extracting data using learned patterns."""
        # Setup browser mock
        mock_instance = mock_browser.return_value
        mock_instance.driver.page_source = self.product_html
        mock_instance.get.return_value = True
        
        # Create a pattern
        pattern_id = "test_pattern"
        self.scraper.extraction_patterns[pattern_id] = {
            'url': 'https://example.com/product',
            'patterns': [{
                'field': 'title',
                'selector': 'h1.product-title',
                'attribute': 'text',
                'manipulation': None
            }],
            'created_at': '2023-01-01T12:00:00'
        }
        
        # Mock _apply_patterns to return expected data
        with patch.object(self.scraper, '_apply_patterns') as mock_apply:
            mock_apply.return_value = {
                'title': 'Premium Headphones',
                'price': '$199.99'
            }
            
            # Test extraction
            result = self.scraper.extract_similar("https://example.com/similar-product", pattern_id)
            
            # Assertions
            self.assertEqual(result['status'], 'success')
            self.assertEqual(result['data']['title'], 'Premium Headphones')
            self.assertTrue('result_path' in result)

if __name__ == '__main__':
    unittest.main()
