"""
Unit tests for the memory manager module.

This test suite validates memory monitoring, chunking operations,
and memory optimization features of the memory manager.
"""

import os
import unittest
import tempfile
import shutil
import time
import gc
import threading
from unittest.mock import patch, MagicMock, call

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraping_project.memory_manager import MemoryManager, get_memory_manager

class TestMemoryManager(unittest.TestCase):
    """Test case for MemoryManager class."""
    
    def setUp(self):
        """Set up test environment before each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.memory_manager = MemoryManager(
            warning_threshold=80.0,
            critical_threshold=90.0,
            monitor_interval=0.1,  # Short interval for testing
            auto_gc=True,
            temp_dir=self.temp_dir
        )
    
    def tearDown(self):
        """Clean up after each test."""
        # Stop monitoring if running
        if self.memory_manager.monitoring:
            self.memory_manager.stop_monitoring()
        
        # Clean up temporary directory
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('psutil.virtual_memory')
    @patch('psutil.Process')
    def test_get_memory_usage(self, mock_process, mock_virtual_memory):
        """Test memory usage information retrieval."""
        # Mock psutil responses
        mock_virtual_memory.return_value.percent = 75.0
        mock_virtual_memory.return_value.used = 8000000000  # 8 GB
        mock_virtual_memory.return_value.total = 16000000000  # 16 GB
        
        mock_process_instance = MagicMock()
        mock_process_instance.memory_info.return_value.rss = 500000000  # 500 MB
        mock_process_instance.memory_info.return_value.vms = 1000000000  # 1 GB
        mock_process.return_value = mock_process_instance
        
        # Get memory usage
        usage = self.memory_manager.get_memory_usage()
        
        # Assertions
        self.assertEqual(usage['system_percent'], 75.0)
        self.assertAlmostEqual(usage['system_used_mb'], 7629.39, places=2)
        self.assertAlmostEqual(usage['system_total_mb'], 15258.79, places=2)
        self.assertAlmostEqual(usage['process_rss_mb'], 476.84, places=2)
        self.assertAlmostEqual(usage['process_vms_mb'], 953.67, places=2)
    
    @patch('gc.collect')
    @patch('scraping_project.memory_manager.MemoryManager.get_memory_usage')
    def test_force_garbage_collection(self, mock_get_memory_usage, mock_gc_collect):
        """Test forced garbage collection."""
        # Mock memory usage before and after GC
        mock_get_memory_usage.side_effect = [
            # Before GC
            {
                'system_percent': 75.0,
                'system_used_mb': 12000,
                'system_total_mb': 16000,
                'process_rss_mb': 500,
                'process_vms_mb': 1000
            },
            # After GC
            {
                'system_percent': 70.0,
                'system_used_mb': 11200,
                'system_total_mb': 16000,
                'process_rss_mb': 450,
                'process_vms_mb': 900
            }
        ]
        
        # Call garbage collection
        result = self.memory_manager.force_garbage_collection()
        
        # Assertions
        mock_gc_collect.assert_called_once_with(generation=2)
        self.assertEqual(result['mb_freed'], 50)  # 500 - 450
        self.assertEqual(result['percent_freed'], 10.0)  # (50/500) * 100
    
    def test_chunk_operation(self):
        """Test chunking of large operations."""
        # Create a large list
        items = list(range(1000))
        
        # Set up the _check_memory mock
        with patch.object(self.memory_manager, '_check_memory') as mock_check:
            # Get chunks
            chunks = list(self.memory_manager.chunk_operation(items, chunk_size=100))
            
            # Assertions
            self.assertEqual(len(chunks), 10)  # 1000/100 = 10 chunks
            self.assertEqual(len(chunks[0]), 100)
            self.assertEqual(chunks[0][0], 0)
            self.assertEqual(chunks[9][99], 999)  # Last element
            
            # Check that _check_memory was called for each chunk
            self.assertEqual(mock_check.call_count, 10)
    
    def test_offload_to_disk_and_load_from_disk(self):
        """Test offloading data to disk and loading it back."""
        # Create test data
        test_data = {"key1": "value1", "key2": [1, 2, 3], "key3": {"nested": "data"}}
        
        # Offload to disk
        filepath = self.memory_manager.offload_to_disk(test_data, prefix="test_data")
        
        # Assertions for offload
        self.assertTrue(os.path.exists(filepath))
        self.assertIn(filepath, self.memory_manager.temp_files)
        self.assertTrue(filepath.startswith(self.memory_manager.scrapy_temp_dir))
        self.assertTrue(filepath.endswith(".pickle"))
        
        # Load from disk
        loaded_data = self.memory_manager.load_from_disk(filepath)
        
        # Assertions for loaded data
        self.assertEqual(loaded_data, test_data)
        self.assertEqual(loaded_data["key1"], "value1")
        self.assertEqual(loaded_data["key2"], [1, 2, 3])
        self.assertEqual(loaded_data["key3"]["nested"], "data")
        
        # Test removing the temp file
        self.assertTrue(self.memory_manager.remove_temp_file(filepath))
        self.assertFalse(os.path.exists(filepath))
        self.assertNotIn(filepath, self.memory_manager.temp_files)
    
    def test_memory_safe_operation_context_manager(self):
        """Test the memory_safe_operation context manager."""
        # Mock get_memory_usage and force_garbage_collection
        with patch.object(self.memory_manager, 'get_memory_usage') as mock_get_memory, \
             patch.object(self.memory_manager, 'force_garbage_collection') as mock_gc:
            
            # Mock memory usage with high values to trigger GC
            mock_get_memory.side_effect = [
                # Before operation
                {
                    'system_percent': 70.0,
                    'process_rss_mb': 400
                },
                # After operation
                {
                    'system_percent': 85.0,  # Higher than warning threshold
                    'process_rss_mb': 600
                }
            ]
            
            # Use context manager
            with self.memory_manager.memory_safe_operation("test_operation"):
                # Operation code here
                pass
            
            # Assertions
            mock_get_memory.assert_called()
            mock_gc.assert_called_once()  # Should be called due to high memory
    
    def test_paginate_results(self):
        """Test pagination of large result sets."""
        # Create test data
        items = [{"index": i} for i in range(200)]
        
        # Test with normal pagination (not offloading)
        result = self.memory_manager.paginate_results(items, page_size=50)
        
        # Assertions
        self.assertEqual(result['total'], 200)
        self.assertEqual(result['pages'], 4)
        self.assertEqual(result['page_size'], 50)
        self.assertEqual(len(result['items']), 50)
        self.assertEqual(result['items'][0]['index'], 0)
        self.assertEqual(result['items'][49]['index'], 49)
        
        # Test getting pages
        page1 = self.memory_manager.get_page(result, 1)
        page2 = self.memory_manager.get_page(result, 2)
        
        self.assertEqual(len(page1), 50)
        self.assertEqual(page1[0]['index'], 0)
        
        # Test with small result set
        small_items = [{"index": i} for i in range(5)]
        small_result = self.memory_manager.paginate_results(small_items, page_size=10)
        
        self.assertEqual(small_result['total'], 5)
        self.assertEqual(small_result['pages'], 1)
        self.assertEqual(len(small_result['items']), 5)
    
    @patch('threading.Thread')
    def test_start_monitoring_and_stop_monitoring(self, mock_thread):
        """Test starting and stopping the monitoring thread."""
        # Start monitoring
        self.memory_manager.start_monitoring()
        
        # Assertions for start_monitoring
        self.assertTrue(self.memory_manager.monitoring)
        mock_thread.assert_called_once()
        mock_thread_instance = mock_thread.return_value
        mock_thread_instance.start.assert_called_once()
        
        # Stop monitoring
        with patch.object(self.memory_manager, '_cleanup_temp_files') as mock_cleanup:
            self.memory_manager.stop_monitoring()
            
            # Assertions for stop_monitoring
            self.assertFalse(self.memory_manager.monitoring)
            mock_cleanup.assert_called_once()

    def test_memory_manager_as_context_manager(self):
        """Test using MemoryManager as a context manager."""
        with patch.object(MemoryManager, 'start_monitoring') as mock_start, \
             patch.object(MemoryManager, 'stop_monitoring') as mock_stop:
            
            with self.memory_manager as mm:
                # Check that it's the same instance
                self.assertEqual(mm, self.memory_manager)
                mock_start.assert_called_once()
                mock_stop.assert_not_called()
            
            # After context block
            mock_stop.assert_called_once()

if __name__ == '__main__':
    unittest.main()
