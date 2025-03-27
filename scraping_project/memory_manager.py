"""
Memory management utilities to prevent Out of Memory (OOM) errors during scraping operations.

This module provides memory monitoring, chunking of large operations, and garbage
collection optimization to keep memory usage under control during large scraping jobs.
"""

import os
import gc
import time
import logging
import threading
import tracemalloc
import psutil
from typing import Any, Callable, Dict, List, Optional, Union, Generator, TypeVar
from functools import wraps
import tempfile
import json
import pickle
from contextlib import contextmanager

# For type hints
T = TypeVar('T')

logger = logging.getLogger(__name__)

class MemoryManager:
    """
    Memory management for preventing OOM errors in scraping operations.
    
    Provides utilities for:
    - Memory monitoring
    - Memory-safe operation chunking
    - Offloading large data to disk
    - Garbage collection optimization
    """
    
    def __init__(
        self, 
        warning_threshold: float = 80.0,  # % of system memory
        critical_threshold: float = 90.0,  # % of system memory
        monitor_interval: float = 5.0,     # seconds
        auto_gc: bool = True,
        temp_dir: Optional[str] = None
    ):
        """
        Initialize the memory manager.
        
        Args:
            warning_threshold: Memory usage percentage at which to log warnings
            critical_threshold: Memory usage percentage at which to take action
            monitor_interval: Interval between memory checks in seconds
            auto_gc: Whether to automatically run garbage collection when needed
            temp_dir: Directory for temporary files (uses system temp if None)
        """
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self.monitor_interval = monitor_interval
        self.auto_gc = auto_gc
        self.temp_dir = temp_dir or tempfile.gettempdir()
        
        # Create a dedicated directory for our temp files
        self.scrapy_temp_dir = os.path.join(self.temp_dir, 'scrapy_memory_manager')
        os.makedirs(self.scrapy_temp_dir, exist_ok=True)
        
        # Init memory monitoring
        self.monitoring = False
        self.monitor_thread = None
        self.temp_files = []
        
        # Process info
        self.process = psutil.Process(os.getpid())
        
        logger.info(f"Memory Manager initialized with warning threshold: {warning_threshold}%, "
                   f"critical threshold: {critical_threshold}%")
    
    def start_monitoring(self):
        """Start memory usage monitoring in a background thread."""
        if self.monitoring:
            return
            
        self.monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._memory_monitor_thread,
            daemon=True
        )
        self.monitor_thread.start()
        logger.info("Memory monitoring started")
        
    def stop_monitoring(self):
        """Stop the memory monitoring thread."""
        self.monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2.0)
            
        # Clean up any temporary files
        self._cleanup_temp_files()
        logger.info("Memory monitoring stopped")
    
    def get_memory_usage(self) -> Dict[str, float]:
        """
        Get current memory usage information.
        
        Returns:
            Dict with memory usage percentages and values in MB
        """
        # System memory usage
        system = psutil.virtual_memory()
        
        # Process memory usage (this Python process)
        process_info = self.process.memory_info()
        
        return {
            "system_percent": system.percent,
            "system_used_mb": system.used / (1024 * 1024),
            "system_total_mb": system.total / (1024 * 1024),
            "process_rss_mb": process_info.rss / (1024 * 1024),
            "process_vms_mb": process_info.vms / (1024 * 1024),
        }
    
    def force_garbage_collection(self) -> Dict[str, Any]:
        """
        Force full garbage collection and return stats.
        
        Returns:
            Dict with garbage collection results
        """
        # Get memory usage before GC
        before = self.get_memory_usage()
        
        # Force garbage collection
        gc.collect(generation=2)  # Force full collection
        
        # Get memory usage after GC
        after = self.get_memory_usage()
        
        results = {
            "before": before,
            "after": after,
            "mb_freed": before["process_rss_mb"] - after["process_rss_mb"],
            "percent_freed": (before["process_rss_mb"] - after["process_rss_mb"]) / 
                             (before["process_rss_mb"] or 1) * 100
        }
        
        logger.info(f"Garbage collection freed {results['mb_freed']:.2f} MB "
                   f"({results['percent_freed']:.2f}% of process memory)")
                   
        return results
    
    def chunk_operation(self, items: List[T], chunk_size: int = 100) -> Generator[List[T], None, None]:
        """
        Split a large operation into smaller chunks to prevent memory issues.
        
        Args:
            items: List of items to process
            chunk_size: Size of each chunk
            
        Yields:
            Chunks of the original list
        """
        for i in range(0, len(items), chunk_size):
            # Check memory between chunks
            self._check_memory()
            yield items[i:i + chunk_size]
    
    def offload_to_disk(self, data: Any, prefix: str = "scrapy_data") -> str:
        """
        Offload large data to disk temporarily to free memory.
        
        Args:
            data: Data object to offload
            prefix: Prefix for the temporary file name
            
        Returns:
            Path to the temporary file
        """
        try:
            fd, temp_path = tempfile.mkstemp(
                prefix=f"{prefix}_",
                suffix=".pickle",
                dir=self.scrapy_temp_dir
            )
            os.close(fd)  # Close the file descriptor
            
            with open(temp_path, 'wb') as f:
                pickle.dump(data, f)
                
            self.temp_files.append(temp_path)
            
            # Suggest garbage collection
            if self.auto_gc:
                gc.collect()
                
            return temp_path
            
        except Exception as e:
            logger.error(f"Error offloading data to disk: {e}")
            raise
    
    def load_from_disk(self, filepath: str) -> Any:
        """
        Load previously offloaded data from disk.
        
        Args:
            filepath: Path to the temporary file
            
        Returns:
            The loaded data object
        """
        try:
            with open(filepath, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            logger.error(f"Error loading data from disk: {e}")
            raise
    
    def remove_temp_file(self, filepath: str) -> bool:
        """Remove a temporary file created by offload_to_disk."""
        try:
            if filepath in self.temp_files and os.path.exists(filepath):
                os.remove(filepath)
                self.temp_files.remove(filepath)
                return True
            return False
        except Exception as e:
            logger.error(f"Error removing temporary file {filepath}: {e}")
            return False
    
    @contextmanager
    def memory_safe_operation(self, operation_name: str):
        """
        Context manager for memory-intensive operations.
        
        Monitors memory before and after the operation, and triggers garbage collection
        if memory usage exceeds thresholds.
        
        Args:
            operation_name: Name of the operation for logging
        """
        usage_before = self.get_memory_usage()
        logger.debug(f"Starting memory-intensive operation: {operation_name} "
                    f"(Memory: {usage_before['process_rss_mb']:.2f} MB)")
        
        try:
            # Start memory tracking
            tracemalloc.start()
            
            # Execute the operation
            yield
            
        finally:
            # Get memory usage stats
            usage_after = self.get_memory_usage()
            memory_delta = usage_after["process_rss_mb"] - usage_before["process_rss_mb"]
            
            # Get tracemalloc stats
            snapshot = tracemalloc.take_snapshot()
            tracemalloc.stop()
            
            logger.debug(f"Completed operation: {operation_name} "
                        f"(Memory delta: {memory_delta:.2f} MB)")
            
            # Check if memory usage is high and run GC if needed
            if usage_after["system_percent"] > self.warning_threshold and self.auto_gc:
                logger.info(f"High memory usage after {operation_name}, running garbage collection")
                self.force_garbage_collection()
            
            # Log the top memory allocations if significant memory was used
            if memory_delta > 50:  # 50MB threshold for detailed tracking
                top_stats = snapshot.statistics('lineno')
                logger.debug("Top 5 memory allocations:")
                for stat in top_stats[:5]:
                    logger.debug(f"{stat}")
    
    def memory_safe_function(self, func):
        """
        Decorator for memory-intensive functions.
        
        Args:
            func: Function to wrap with memory safety
            
        Returns:
            Wrapped function
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            with self.memory_safe_operation(func.__name__):
                return func(*args, **kwargs)
        return wrapper
    
    def paginate_results(self, results: List[T], page_size: int = 50) -> Dict[str, Union[int, List[T]]]:
        """
        Paginate large result sets to avoid memory issues when serving data.
        
        Args:
            results: Full list of results
            page_size: Number of items per page
            
        Returns:
            Dict with pagination info and current page items
        """
        if len(results) <= page_size:
            return {
                "total": len(results),
                "pages": 1,
                "page_size": page_size,
                "items": results
            }
        
        # If we have too many results, offload to disk
        if len(results) > 1000:
            temp_path = self.offload_to_disk(results)
            return {
                "total": len(results),
                "pages": (len(results) + page_size - 1) // page_size,
                "page_size": page_size,
                "offloaded": True,
                "temp_path": temp_path
            }
        
        return {
            "total": len(results),
            "pages": (len(results) + page_size - 1) // page_size,
            "page_size": page_size,
            "items": results[:page_size]
        }
    
    def get_page(self, pagination_info: Dict[str, Any], page: int) -> List[T]:
        """
        Get a specific page from paginated results.
        
        Args:
            pagination_info: Pagination info from paginate_results
            page: Page number (1-based)
            
        Returns:
            Items for the requested page
        """
        if page < 1:
            page = 1
        elif page > pagination_info.get("pages", 1):
            page = pagination_info.get("pages", 1)
        
        page_size = pagination_info.get("page_size", 50)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        
        # If data was offloaded, load from disk
        if pagination_info.get("offloaded", False):
            temp_path = pagination_info.get("temp_path")
            all_items = self.load_from_disk(temp_path)
            return all_items[start_idx:end_idx]
        
        # Otherwise fetch from the original items
        items = pagination_info.get("items", [])
        if isinstance(items, list) and start_idx < len(items):
            if "total" in pagination_info and pagination_info["total"] > len(items):
                # This pagination object only contains the first page
                if page > 1:
                    logger.warning("Attempted to get page beyond first page from incomplete pagination object")
                    return []
            return items[start_idx:end_idx]
            
        return []
    
    def get_current_usage_summary(self) -> Dict[str, Any]:
        """
        Get a summary of current memory usage with recommendations.
        
        Returns:
            Dict with usage info and recommendations
        """
        usage = self.get_memory_usage()
        
        # Check for Python-specific memory stats
        gc_counts = gc.get_count()
        gc_threshold = gc.get_threshold()
        
        recommendations = []
        if usage["system_percent"] > self.critical_threshold:
            recommendations.append("CRITICAL: System memory usage is very high. Consider terminating "
                                 "some processes or reducing the scope of current operations.")
        elif usage["system_percent"] > self.warning_threshold:
            recommendations.append("WARNING: System memory usage is high. Consider running garbage "
                                 "collection or reducing the size of data being processed.")
        
        # Check if garbage collection is needed
        if gc_counts[0] > gc_threshold[0] * 0.8:
            recommendations.append("Consider running manual garbage collection to free memory.")
        
        # Create report
        return {
            "timestamp": time.time(),
            "usage": usage,
            "gc_info": {
                "counts": gc_counts,
                "threshold": gc_threshold,
                "enabled": gc.isenabled()
            },
            "recommendations": recommendations,
            "status": "critical" if usage["system_percent"] > self.critical_threshold else 
                     "warning" if usage["system_percent"] > self.warning_threshold else "ok"
        }
    
    def _memory_monitor_thread(self):
        """Background thread that monitors memory usage."""
        while self.monitoring:
            try:
                usage = self.get_memory_usage()
                
                if usage["system_percent"] > self.critical_threshold:
                    logger.critical(f"CRITICAL: Memory usage at {usage['system_percent']}% "
                                  f"({usage['process_rss_mb']:.2f} MB used by this process)")
                    # Critical action - force GC
                    if self.auto_gc:
                        self.force_garbage_collection()
                        
                elif usage["system_percent"] > self.warning_threshold:
                    logger.warning(f"High memory usage: {usage['system_percent']}% "
                                 f"({usage['process_rss_mb']:.2f} MB used by this process)")
                    # Warning level - suggest GC
                    if self.auto_gc and usage["system_percent"] > (self.warning_threshold + 5):
                        self.force_garbage_collection()
                        
            except Exception as e:
                logger.error(f"Error in memory monitor thread: {e}")
                
            time.sleep(self.monitor_interval)
    
    def _check_memory(self):
        """Check current memory usage and take action if needed."""
        usage = self.get_memory_usage()
        
        if usage["system_percent"] > self.critical_threshold:
            logger.warning(f"Critical memory usage detected: {usage['system_percent']}%")
            # Take drastic action - force garbage collection
            if self.auto_gc:
                self.force_garbage_collection()
        elif usage["system_percent"] > self.warning_threshold:
            logger.info(f"High memory usage detected: {usage['system_percent']}%")
            # Consider garbage collection
            if self.auto_gc:
                gc.collect()
    
    def _cleanup_temp_files(self):
        """Clean up all temporary files created by this memory manager."""
        for filepath in self.temp_files[:]:
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
                    self.temp_files.remove(filepath)
            except Exception as e:
                logger.error(f"Error removing temporary file {filepath}: {e}")
    
    def __enter__(self):
        """Context manager enter."""
        self.start_monitoring()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop_monitoring()


# Global singleton instance
_memory_manager = None

def get_memory_manager() -> MemoryManager:
    """Get the global memory manager instance."""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager
