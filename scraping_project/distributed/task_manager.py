"""
Distributed task manager for Scrapy.

This module implements a distributed task system using Celery and Redis,
allowing scraping jobs to be distributed across multiple worker nodes.
"""

import os
import logging
import json
import time
from datetime import datetime
from celery import Celery, signals
from celery.result import AsyncResult
from typing import Dict, List, Any, Optional, Union, Tuple

from ..config import Config
from ..memory_manager import get_memory_manager
from ..db_manager import DatabaseManager
from ..error_handler import error_context, log_error_to_file, ScrapyError

# Configure logging
logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery(
    'scrapy_tasks',
    broker=os.environ.get('REDIS_URL', 'redis://localhost:6379/0'),
    backend=os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
)

# Configure Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    enable_utc=True,
    worker_max_tasks_per_child=100,  # Restart worker after 100 tasks to prevent memory leaks
    worker_prefetch_multiplier=1,    # Don't prefetch tasks for better distribution
    task_acks_late=True,             # Task acknowledged after execution
    task_track_started=True,         # Track when tasks are started
    task_time_limit=3600 * 2,        # 2 hour timeout for tasks
    task_soft_time_limit=3600,       # 1 hour soft timeout
    worker_send_task_events=True,    # Send task-related events for monitoring
    task_send_sent_event=True,       # Track when tasks are sent
)

# Database manager for task persistence
db_manager = DatabaseManager()

# Memory Manager for resource monitoring
memory_manager = get_memory_manager()

class TaskStatus:
    """Task status constants."""
    PENDING = 'PENDING'
    RECEIVED = 'RECEIVED' 
    STARTED = 'STARTED'
    SUCCESS = 'SUCCESS'
    FAILURE = 'FAILURE'
    REVOKED = 'REVOKED'
    RETRY = 'RETRY'
    REJECTED = 'REJECTED'

@celery_app.task(bind=True, name='scrape_website')
def scrape_website_task(self, url: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Celery task to scrape a website.
    
    Args:
        url: URL to scrape
        options: Dictionary of scraper options
        
    Returns:
        Dictionary with scraping results
    """
    from ..general_webscraper import WebpageScraper
    
    options = options or {}
    task_id = self.request.id
    
    logger.info(f"Starting scrape task {task_id} for URL: {url}")
    
    # Update task status in database
    db_manager.update_distributed_task(
        task_id=task_id,
        status=TaskStatus.STARTED,
        progress=0,
        metadata={"url": url, "options": options}
    )
    
    # Start memory monitoring for this task
    memory_manager.start_monitoring()
    
    try:
        # Initialize and run scraper
        scraper = WebpageScraper(
            output_dir=os.path.join(Config.SCRAPE_OUTPUT_DIR, f"task_{task_id}")
        )
        
        # Create a progress callback
        def progress_callback(current, total):
            percent = int((current / total) * 100) if total > 0 else 0
            self.update_state(
                state=TaskStatus.STARTED,
                meta={'current': current, 'total': total, 'percent': percent}
            )
            # Update task in database
            db_manager.update_distributed_task(
                task_id=task_id,
                progress=percent
            )
        
        # Run the scraper with progress tracking
        result = scraper.save_webpage(
            url=url,
            follow_links=options.get('follow_links', False),
            compile_text=options.get('compile_text', False),
            max_pages=options.get('max_pages', 10),
            progress_callback=progress_callback
        )
        
        # Save result to database
        success = result.get('status') == 'success'
        db_manager.update_distributed_task(
            task_id=task_id,
            status=TaskStatus.SUCCESS if success else TaskStatus.FAILURE,
            progress=100 if success else 0,
            result_data=result,
            completed_at=datetime.now().isoformat()
        )
        
        logger.info(f"Completed scrape task {task_id} for URL: {url}")
        return result
        
    except Exception as e:
        logger.error(f"Error in scrape task {task_id}: {str(e)}")
        error_log = log_error_to_file(e)
        
        # Update task status in database
        db_manager.update_distributed_task(
            task_id=task_id,
            status=TaskStatus.FAILURE,
            metadata={
                "error": str(e),
                "error_log": error_log
            },
            completed_at=datetime.now().isoformat()
        )
        
        # Re-raise the exception for Celery to handle
        raise
    finally:
        # Stop memory monitoring
        memory_manager.stop_monitoring()

@celery_app.task(bind=True, name='recursive_scrape')
def recursive_scrape_task(self, url: str, config: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Celery task to perform a recursive scrape.
    
    Args:
        url: Starting URL for recursive scrape
        config: Configuration for the recursive scraper
        
    Returns:
        Dictionary with scraping results
    """
    from ..recursive_scraper import RecursiveScraper
    
    config = config or {}
    task_id = self.request.id
    
    logger.info(f"Starting recursive scrape task {task_id} for URL: {url}")
    
    # Update task status in database
    db_manager.update_distributed_task(
        task_id=task_id,
        status=TaskStatus.STARTED,
        progress=0,
        metadata={"url": url, "config": config}
    )
    
    # Start memory monitoring
    memory_manager.start_monitoring()
    
    try:
        # Initialize and run recursive scraper
        scraper = RecursiveScraper(
            output_dir=os.path.join(Config.SCRAPE_OUTPUT_DIR, f"task_{task_id}"),
            config=config
        )
        
        # Create a progress callback for the recursive scraper
        def progress_callback(pages_crawled, max_pages):
            percent = int((pages_crawled / max_pages) * 100) if max_pages > 0 else 0
            self.update_state(
                state=TaskStatus.STARTED,
                meta={'crawled': pages_crawled, 'total': max_pages, 'percent': percent}
            )
            # Update task in database
            db_manager.update_distributed_task(
                task_id=task_id,
                progress=percent
            )
        
        # Set the progress callback in the scraper's config
        scraper.set_progress_callback(progress_callback)
        
        # Run the scraper
        result = scraper.start_crawl(url)
        
        # Save result to database
        success = result.get('status') == 'success'
        db_manager.update_distributed_task(
            task_id=task_id,
            status=TaskStatus.SUCCESS if success else TaskStatus.FAILURE,
            progress=100 if success else 0,
            result_data=result,
            completed_at=datetime.now().isoformat()
        )
        
        logger.info(f"Completed recursive scrape task {task_id} for URL: {url}")
        return result
        
    except Exception as e:
        logger.error(f"Error in recursive scrape task {task_id}: {str(e)}")
        error_log = log_error_to_file(e)
        
        # Update task status in database
        db_manager.update_distributed_task(
            task_id=task_id,
            status=TaskStatus.FAILURE,
            metadata={
                "error": str(e),
                "error_log": error_log
            },
            completed_at=datetime.now().isoformat()
        )
        
        # Re-raise the exception for Celery to handle
        raise
    finally:
        # Stop memory monitoring
        memory_manager.stop_monitoring()

class TaskManager:
    """
    Manages distributed scraping tasks.
    
    This class provides high-level methods to submit, monitor, and manage
    distributed scraping tasks across multiple workers.
    """
    
    def __init__(self):
        """Initialize the task manager."""
        self.db_manager = db_manager
    
    def submit_scrape_task(self, url: str, options: Dict[str, Any] = None) -> str:
        """
        Submit a scraping task to the task queue.
        
        Args:
            url: URL to scrape
            options: Dictionary of scraper options
            
        Returns:
            Task ID
        """
        # Create task in database first
        task_record_id = self.db_manager.create_distributed_task(
            task_type="scrape_website",
            status=TaskStatus.PENDING,
            metadata={"url": url, "options": options}
        )
        
        # Submit task to Celery
        task = scrape_website_task.apply_async(
            args=[url],
            kwargs={"options": options},
            task_id=str(task_record_id)  # Use the DB ID as the Celery task ID
        )
        
        return task.id
    
    def submit_recursive_scrape_task(self, url: str, config: Dict[str, Any] = None) -> str:
        """
        Submit a recursive scraping task to the task queue.
        
        Args:
            url: Starting URL for recursive scrape
            config: Configuration for the recursive scraper
            
        Returns:
            Task ID
        """
        # Create task in database first
        task_record_id = self.db_manager.create_distributed_task(
            task_type="recursive_scrape",
            status=TaskStatus.PENDING,
            metadata={"url": url, "config": config}
        )
        
        # Submit task to Celery
        task = recursive_scrape_task.apply_async(
            args=[url],
            kwargs={"config": config},
            task_id=str(task_record_id)  # Use the DB ID as the Celery task ID
        )
        
        return task.id
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get the current status of a task.
        
        Args:
            task_id: ID of the task
            
        Returns:
            Dictionary with task status information
        """
        # Get task status from database
        db_task = self.db_manager.get_distributed_task(task_id)
        
        if not db_task:
            return {"status": "NOT_FOUND"}
        
        # Check if we need to update from Celery
        if db_task['status'] in [TaskStatus.PENDING, TaskStatus.STARTED, TaskStatus.RECEIVED]:
            # Get current status from Celery
            celery_task = AsyncResult(task_id, app=celery_app)
            
            # If status has changed, update the database
            if celery_task.state != db_task['status']:
                self.db_manager.update_distributed_task(
                    task_id=task_id,
                    status=celery_task.state,
                    metadata=celery_task.info if isinstance(celery_task.info, dict) else None
                )
                
                # Update our local copy of the task data
                db_task = self.db_manager.get_distributed_task(task_id)
        
        return db_task
    
    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a running or pending task.
        
        Args:
            task_id: ID of the task
            
        Returns:
            True if task was successfully canceled
        """
        # Revoke the task in Celery
        celery_task = AsyncResult(task_id, app=celery_app)
        celery_task.revoke(terminate=True)
        
        # Update status in database
        self.db_manager.update_distributed_task(
            task_id=task_id,
            status=TaskStatus.REVOKED,
            completed_at=datetime.now().isoformat()
        )
        
        return True
    
    def get_active_tasks(self) -> List[Dict[str, Any]]:
        """
        Get a list of all active tasks.
        
        Returns:
            List of task dictionaries
        """
        # Get active tasks from database
        active_statuses = [TaskStatus.PENDING, TaskStatus.RECEIVED, TaskStatus.STARTED]
        return self.db_manager.get_distributed_tasks_by_status(active_statuses)
    
    def get_recent_tasks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get a list of recent tasks.
        
        Args:
            limit: Maximum number of tasks to return
            
        Returns:
            List of task dictionaries
        """
        return self.db_manager.get_recent_distributed_tasks(limit)
    
    def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the result of a completed task.
        
        Args:
            task_id: ID of the task
            
        Returns:
            Task result data or None if task is not complete
        """
        task = self.db_manager.get_distributed_task(task_id)
        
        if not task:
            return None
            
        if task['status'] != TaskStatus.SUCCESS:
            return None
            
        return task.get('result_data')
    
    def get_worker_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the current workers.
        
        Returns:
            Dictionary with worker statistics
        """
        # This would typically be implemented using Celery's inspect functionality
        # but for simplicity we'll use a more basic approach
        try:
            inspect = celery_app.control.inspect()
            stats = {
                "active_workers": 0,
                "queued_tasks": 0,
                "running_tasks": 0,
                "worker_details": {}
            }
            
            # Get active workers
            active = inspect.active() or {}
            stats["active_workers"] = len(active)
            
            # Count running tasks
            running_tasks = 0
            for worker_name, tasks in active.items():
                running_tasks += len(tasks)
                stats["worker_details"][worker_name] = {
                    "running_tasks": len(tasks),
                    "tasks": tasks
                }
            
            stats["running_tasks"] = running_tasks
            
            # Get queued tasks
            scheduled = inspect.scheduled() or {}
            reserved = inspect.reserved() or {}
            
            queued_tasks = 0
            for worker_name, tasks in scheduled.items():
                queued_tasks += len(tasks)
                if worker_name in stats["worker_details"]:
                    stats["worker_details"][worker_name]["scheduled_tasks"] = len(tasks)
                else:
                    stats["worker_details"][worker_name] = {"scheduled_tasks": len(tasks)}
            
            for worker_name, tasks in reserved.items():
                queued_tasks += len(tasks)
                if worker_name in stats["worker_details"]:
                    stats["worker_details"][worker_name]["reserved_tasks"] = len(tasks)
                else:
                    stats["worker_details"][worker_name] = {"reserved_tasks": len(tasks)}
            
            stats["queued_tasks"] = queued_tasks
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting worker stats: {e}")
            return {
                "error": str(e),
                "active_workers": 0,
                "queued_tasks": 0,
                "running_tasks": 0
            }

# Global task manager instance
_task_manager = None

def get_task_manager() -> TaskManager:
    """Get the global task manager instance."""
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager

@signals.task_prerun.connect
def task_prerun_handler(task_id, task, *args, **kwargs):
    """Handler called before a task is run."""
    logger.info(f"Starting task {task.name}[{task_id}]")

@signals.task_postrun.connect
def task_postrun_handler(task_id, task, *args, retval=None, state=None, **kwargs):
    """Handler called after a task completes."""
    logger.info(f"Task {task.name}[{task_id}] completed with state {state}")

@signals.task_failure.connect
def task_failure_handler(task_id, exception, *args, **kwargs):
    """Handler called when a task fails."""
    logger.error(f"Task {task_id} failed: {str(exception)}")
    # The task itself already updates the database with the failure status
