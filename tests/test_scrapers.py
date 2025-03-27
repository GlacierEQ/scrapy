import unittest
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraping_project.general_webscraper import WebpageScraper
from scraping_project.recursive_scraper import RecursiveScraper
from scraping_project.data_analyzer import DataAnalyzer

class MockResponse:
    def __init__(self, content, status_code=200):
        self.content = content
        self.status_code = status_code
        self.text = content

class TestWebScraper(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.scraper = WebpageScraper(output_dir=self.temp_dir)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    @patch('selenium.webdriver.Chrome')
    def test_save_webpage_success(self, mock_chrome):
        # Set up mock driver behavior
        mock_driver = MagicMock()
        mock_chrome.return_value = mock_driver
        
        # Mock page source and screenshot
        mock_driver.page_source = "<html><body><h1>Test Page</h1><p>Test content</p></body></html>"
        mock_driver.find_element().text = "Test Page Test content"
        mock_driver.find_elements.return_value = []
        
        # Call the method
        result = self.scraper.save_webpage("http://example.com")
        
        # Assertions
        self.assertEqual(result["status"], "success")
        self.assertIn("data", result)
        self.assertIn("pages", result["data"])
        self.assertEqual(len(result["data"]["pages"]), 1)
    
    @patch('selenium.webdriver.Chrome')
    def test_save_webpage_exception(self, mock_chrome):
        # Make the driver raise an exception
        mock_chrome.side_effect = Exception("Test error")
        
        # Call the method
        result = self.scraper.save_webpage("http://example.com")
        
        # Assertions
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["message"], "Test error")

class TestRecursiveScraper(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.scraper = RecursiveScraper(output_dir=self.temp_dir)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    @patch('selenium.webdriver.Chrome')
    def test_start_crawl(self, mock_chrome):
        # Set up mock driver behavior
        mock_driver = MagicMock()
        mock_chrome.return_value = mock_driver
        
        # Mock page source and screenshot
        mock_driver.page_source = "<html><body><h1>Test Page</h1><p>Test content</p><a href='http://example.com/page2'>Link</a></body></html>"
        
        # Mock presence_of_element_located
        mock_element = MagicMock()
        mock_driver.find_element.return_value = mock_element
        mock_element.text = "Test Page Test content"
        
        # Mock find_elements for links
        mock_link = MagicMock()
        mock_driver.find_elements.return_value = [mock_link]
        mock_link.get_attribute.return_value = "http://example.com/page2"
        mock_link.text = "Link"
        
        # Call the method with limited crawl to avoid lengthy test
        self.scraper.config['max_total_pages'] = 1
        result = self.scraper.start_crawl("http://example.com")
        
        # Assertions
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["data"]["stats"]["pages_crawled"], 1)

class TestDataAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = DataAnalyzer()
        
    def test_analyze_webpage(self):
        html = """
        <html>
        <head>
            <title>Test Page</title>
            <meta name="description" content="Test description">
        </head>
        <body>
            <h1>Testing</h1>
            <p>This is a test paragraph.</p>
            <a href="http://example.com">Link</a>
            <img src="test.jpg" alt="Test Image">
        </body>
        </html>
        """
        
        result = self.analyzer.analyze_webpage(html)
        
        # Check metadata
        self.assertEqual(result["metadata"]["title"], "Test Page")
        self.assertEqual(result["metadata"]["meta_description"], "Test description")
        
        # Check content analysis
        self.assertTrue(result["content_analysis"]["word_count"] > 0)
        self.assertEqual(result["content_analysis"]["headings"]["h1"], 1)
        self.assertEqual(result["content_analysis"]["images"], 1)
        
        # Check link analysis
        self.assertEqual(result["link_analysis"]["total_links"], 1)

if __name__ == '__main__':
    unittest.main()
