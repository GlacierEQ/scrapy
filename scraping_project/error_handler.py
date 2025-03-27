"""
Centralized error handling and recovery strategies for Scrapy.

This module provides utilities for handling errors consistently throughout
the application, with features like retry mechanisms, graceful degradation,
and comprehensive error logging.
"""

import logging
import time
import functools
import traceback
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union
from contextlib import contextmanager
import os
from datetime import datetime

# Setup logger
logger = logging.getLogger(__name__)

class ScrapyError(Exception):
    """Base exception class for Scrapy errors."""
    
    def __init__(self, message: str, original_exception: Optional[Exception] = None):
        self.message = message
        self.original_exception = original_exception
        super().__init__(self.message)

class NetworkError(ScrapyError):
    """Raised when network issues prevent scraping."""
    pass

class ParseError(ScrapyError):
    """Raised when content cannot be parsed correctly."""
    pass

class AuthenticationError(ScrapyError):
    """Raised when authentication fails."""
    pass

class ResourceError(ScrapyError):
    """Raised when a required resource is unavailable."""
    pass

class DatabaseError(ScrapyError):
    """Raised for database operation failures."""
    pass

def retry(
    max_tries: int = 3, 
    delay: float = 1.0, 
    backoff: float = 2.0, 
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    logger: Optional[logging.Logger] = None
) -> Callable:
    """
    Retry decorator with exponential backoff for functions.
    
    Args:
        max_tries: Maximum number of attempts
        delay: Initial delay between retries (seconds)
        backoff: Backoff multiplier
        exceptions: Tuple of exceptions to catch for retry
        logger: Logger instance to use
        
    Returns:
        Decorated function with retry capability
    """
    logger = logger or logging.getLogger(__name__)
    
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            mtries, mdelay = max_tries, delay
            last_exception = None
            
            while mtries > 0:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    mtries -= 1
                    if mtries == 0:
                        logger.error(f"Function {func.__name__} failed after {max_tries} tries. Error: {str(e)}")
                        raise
                    
                    wait = mdelay * (1 + (max_tries - mtries) * 0.1 * (0.5 - random.random()))
                    logger.warning(f"Retry {max_tries - mtries} for function {func.__name__} after {wait:.2f} seconds. Error: {str(e)}")
                    time.sleep(wait)
                    mdelay *= backoff
            
            return func(*args, **kwargs)  # Final attempt
            
        return wrapper
    return decorator

@contextmanager
def error_context(
    operation_name: str, 
    error_handler: Optional[Callable[[Exception], Any]] = None,
    cleanup_func: Optional[Callable[[], None]] = None,
    reraise: bool = True
):
    """
    Context manager for handling errors gracefully.
    
    Args:
        operation_name: Name of the operation for logging
        error_handler: Optional function to handle specific errors
        cleanup_func: Optional function to clean up resources
        reraise: Whether to re-raise the exception
    
    Yields:
        None
    """
    try:
        logger.debug(f"Starting operation: {operation_name}")
        yield
        logger.debug(f"Operation completed successfully: {operation_name}")
    except Exception as e:
        logger.error(f"Error in {operation_name}: {str(e)}")
        logger.debug(f"Exception details: {traceback.format_exc()}")
        
        if error_handler:
            try:
                error_handler(e)
            except Exception as handler_error:
                logger.error(f"Error handler failed for {operation_name}: {str(handler_error)}")
        
        if reraise:
            raise
    finally:
        if cleanup_func:
            try:
                cleanup_func()
            except Exception as cleanup_error:
                logger.error(f"Cleanup failed for {operation_name}: {str(cleanup_error)}")

def log_error_to_file(error: Exception, filepath: Optional[str] = None) -> str:
    """
    Log detailed error information to a file.
    
    Args:
        error: The exception to log
        filepath: Optional specific file path, otherwise generates a timestamped path
        
    Returns:
        Path to the error log file
    """
    if filepath is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        filepath = os.path.join(log_dir, f"error_{timestamp}.log")
    
    with open(filepath, 'w') as f:
        f.write(f"Error: {str(error)}\n\n")
        f.write(f"Timestamp: {datetime.now().isoformat()}\n")
        f.write(f"Python version: {sys.version}\n\n")
        f.write("Traceback:\n")
        f.write(traceback.format_exc())
    
    return filepath

def safe_execute(func: Callable, *args, default_return: Any = None, **kwargs) -> Any:
    """
    Execute a function safely, returning a default value on error.
    
    Args:
        func: Function to execute
        *args: Arguments to pass to the function
        default_return: Value to return if function raises an exception
        **kwargs: Keyword arguments to pass to the function
        
    Returns:
        Function result or default value on error
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Error in safe_execute for {func.__name__}: {str(e)}")
        return default_return

def handle_selenium_errors(driver, operation_name: str) -> Callable[[Exception], None]:
    """
    Create an error handler for Selenium-specific errors.
    
    Args:
        driver: Selenium driver instance
        operation_name: Name of the operation for logging
        
    Returns:
        Error handler function
    """
    def handler(exception):
        try:
            # Take screenshot of the error state
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            screenshot_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'error_screenshots')
            os.makedirs(screenshot_dir, exist_ok=True)
            screenshot_path = os.path.join(screenshot_dir, f"error_{operation_name}_{timestamp}.png")
            
            driver.save_screenshot(screenshot_path)
            logger.info(f"Error screenshot saved to {screenshot_path}")
            
            # Log page source
            source_path = os.path.join(screenshot_dir, f"source_{operation_name}_{timestamp}.html")
            with open(source_path, 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
            logger.info(f"Page source saved to {source_path}")
            
        except Exception as e:
            logger.error(f"Failed to capture error state: {str(e)}")
    
    return handler
