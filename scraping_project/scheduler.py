"""
Scheduler for automated scraping jobs.

This module provides a scheduler that can run scraping jobs on a recurring
basis according to various scheduling patterns.
"""

import os
import sys
import time
import logging
import threading
import signal
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Tuple, Union
import schedule

from .db_manager import DatabaseManager
from .distributed.task_manager import get_task_manager
from .config import Config
from .error_handler import error_context, retry

# Set up logging
logger = logging.getLogger(__name__)

# Initialize components
db_manager = DatabaseManager()
task_manager = get_task_manager()

class JobScheduler:
    """
    Manages scheduled scraping jobs.
    
    Features:
    - Schedule jobs at specified intervals (hourly, daily, weekly)
    - Schedule one-time jobs at specific dates/times
    - Schedule jobs with cron-like expressions
    - Persist schedules to database
    - Load schedules from database on startup
    """
    
    def __init__(self, db_manager=None, task_manager=None):
        """
        Initialize the scheduler.
        
        Args:
            db_manager: Database manager instance (or None to use default)
            task_manager: Task manager instance (or None to use default)
        """
        self.db_manager = db_manager or DatabaseManager()
        self.task_manager = task_manager or get_task_manager()
        self.running = False
        self.thread = None
        self.schedule = schedule
        self.jobs = {}  # Job ID -> Schedule job
        
        # For storing callback functions by schedule type
        self._run_callbacks = {
            'hourly': self._run_hourly_job,
            'daily': self._run_daily_job,
            'weekly': self._run_weekly_job,
            'monthly': self._run_monthly_job,
            'one_time': self._run_one_time_job
        }
        
        # Signal handling for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("Job scheduler initialized")
    
    def start(self):
        """Start the scheduler."""
        if self.running:
            logger.warning("Scheduler already running")
            return
        
        self.running = True
        
        # Load existing scheduled jobs from database
        self.load_schedules()
        
        # Start the scheduler thread
        self.thread = threading.Thread(target=self._run_scheduler)
        self.thread.daemon = True
        self.thread.start()
        
        logger.info("Job scheduler started")
    
    def stop(self):
        """Stop the scheduler."""
        if not self.running:
            return
            
        logger.info("Stopping job scheduler...")
        self.running = False
        
        if self.thread:
            self.thread.join(timeout=5)
            
        logger.info("Job scheduler stopped")
    
    def add_job(
        self,
        job_name: str,
        url: str,
        schedule_type: str,
        schedule_value: str,
        job_type: str = 'scrape_website',
        options: Dict[str, Any] = None,
        user_id: Optional[int] = None
    ) -> int:
        """
        Add a new scheduled job.
        
        Args:
            job_name: Name for the job
            url: URL to scrape
            schedule_type: Type of schedule (hourly, daily, weekly, monthly, one_time)
            schedule_value: Value for the schedule type (e.g., "08:00" for daily)
            job_type: Type of scraping job (scrape_website or recursive_scrape)
            options: Options for the scraping job
            user_id: Optional user ID for attribution
            
        Returns:
            ID of the created scheduled job
        """
        # Validate schedule type
        if schedule_type not in ['hourly', 'daily', 'weekly', 'monthly', 'one_time']:
            raise ValueError(f"Invalid schedule type: {schedule_type}")
        
        # Validate and prepare schedule value based on type
        schedule_value = self._validate_schedule_value(schedule_type, schedule_value)
        
        # Calculate next run time
        next_run = self._calculate_next_run(schedule_type, schedule_value)
        
        # Create job in database
        job_id = self.db_manager.add_scheduled_job(
            job_name=job_name,
            url=url,
            schedule_type=schedule_type,
            schedule_value=schedule_value,
            user_id=user_id
        )
        
        # Update next run time
        self.db_manager.update_scheduled_job_run(
            job_id=job_id,
            last_run=None,
            next_run=next_run.isoformat()
        )
        
        # Schedule the job
        self._schedule_job(job_id, schedule_type, schedule_value, job_type, url, options)
        
        logger.info(f"Added scheduled job {job_id}: {job_name} ({schedule_type}:{schedule_value})")
        return job_id
    
    def remove_job(self, job_id: int) -> bool:
        """
        Remove a scheduled job.
        
        Args:
            job_id: ID of the job to remove
            
        Returns:
            True if successful, False otherwise
        """
        # Remove from live schedule
        if job_id in self.jobs:
            self.schedule.cancel_job(self.jobs[job_id])
            del self.jobs[job_id]
        
        # Update in database
        try:
            # Mark as inactive instead of deleting
            self.db_manager.update_scheduled_job_status(job_id, is_active=False)
            logger.info(f"Removed scheduled job {job_id}")
            return True
        except Exception as e:
            logger.error(f"Error removing job {job_id}: {e}")
            return False
    
    def get_job(self, job_id: int) -> Dict[str, Any]:
        """
        Get information about a scheduled job.
        
        Args:
            job_id: ID of the job
            
        Returns:
            Dictionary with job information
        """
        return self.db_manager.get_scheduled_job(job_id)
    
    def get_all_jobs(self) -> List[Dict[str, Any]]:
        """
        Get all scheduled jobs.
        
        Returns:
            List of dictionaries with job information
        """
        return self.db_manager.get_all_scheduled_jobs()
    
    def load_schedules(self):
        """Load existing schedules from the database."""
        jobs = self.db_manager.get_active_scheduled_jobs()
        
        for job in jobs:
            job_id = job['id']
            schedule_type = job['schedule_type']
            schedule_value = job['schedule_value']
            url = job['url']
            
            # Default to scrape_website if not specified
            job_type = job.get('job_type', 'scrape_website')
            
            # Parse options if available
            options = {}
            if 'options' in job and job['options']:
                try:
                    if isinstance(job['options'], str):
                        options = json.loads(job['options'])
                    else:
                        options = job['options']
                except:
                    logger.warning(f"Could not parse options for job {job_id}")
            
            # Schedule the job
            self._schedule_job(job_id, schedule_type, schedule_value, job_type, url, options)
            
            logger.info(f"Loaded scheduled job {job_id}: {job['job_name']} ({schedule_type}:{schedule_value})")
    
    def run_pending(self):
        """Run pending jobs immediately."""
        self.schedule.run_pending()
    
    def _run_scheduler(self):
        """Run the scheduler loop."""
        logger.info("Scheduler thread started")
        
        while self.running:
            try:
                self.schedule.run_pending()
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                time.sleep(5)  # Wait before retrying
    
    def _schedule_job(
        self, 
        job_id: int, 
        schedule_type: str, 
        schedule_value: str,
        job_type: str,
        url: str,
        options: Dict[str, Any]
    ):
        """
        Schedule a job with the scheduler.
        
        Args:
            job_id: ID of the job
            schedule_type: Type of schedule
            schedule_value: Value for the schedule
            job_type: Type of scraping job
            url: URL to scrape
            options: Options for the job
        """
        callback = self._run_callbacks.get(schedule_type)
        if not callback:
            logger.error(f"Invalid schedule type: {schedule_type}")
            return
        
        # Create a runner function that will execute the job
        def job_runner():
            self._execute_job(job_id, job_type, url, options)
        
        # Schedule based on type
        scheduled_job = callback(job_runner, schedule_value)
        
        # Store the scheduled job for later cancellation if needed
        self.jobs[job_id] = scheduled_job
    
    def _run_hourly_job(self, job_func: Callable, minutes: str) -> schedule.Job:
        """
        Schedule a job to run hourly at the specified minutes.
        
        Args:
            job_func: Function to run
            minutes: Minutes past the hour (e.g., "15" for :15, "15,45" for :15 and :45)
            
        Returns:
            Scheduled job
        """
        if ',' in minutes:
            # Multiple times per hour
            minute_values = [int(m.strip()) for m in minutes.split(',')]
            job = None
            
            # Schedule each minute
            for minute in minute_values:
                if job is None:
                    job = self.schedule.every().hour.at(f":{minute:02d}").do(job_func)
                else:
                    self.schedule.every().hour.at(f":{minute:02d}").do(job_func)
            return job
        else:
            # Single time per hour
            return self.schedule.every().hour.at(f":{int(minutes):02d}").do(job_func)
    
    def _run_daily_job(self, job_func: Callable, time_str: str) -> schedule.Job:
        """
        Schedule a job to run daily at the specified time.
        
        Args:
            job_func: Function to run
            time_str: Time of day (e.g., "08:00")
            
        Returns:
            Scheduled job
        """
        return self.schedule.every().day.at(time_str).do(job_func)
    
    def _run_weekly_job(self, job_func: Callable, day_time_str: str) -> schedule.Job:
        """
        Schedule a job to run weekly at the specified day and time.
        
        Args:
            job_func: Function to run
            day_time_str: Day and time (e.g., "monday,08:00")
            
        Returns:
            Scheduled job
        """
        day, time_str = day_time_str.split(',')
        return getattr(self.schedule.every(), day.lower()).at(time_str).do(job_func)
    
    def _run_monthly_job(self, job_func: Callable, day_time_str: str) -> schedule.Job:
        """
        Schedule a job to run monthly at the specified day and time.
        
        Args:
            job_func: Function to run
            day_time_str: Day and time (e.g., "1,08:00" for 1st day of month at 08:00)
            
        Returns:
            Scheduled job
        """
        day, time_str = day_time_str.split(',')
        day = int(day)
        
        def monthly_job():
            today = datetime.now().day
            if today == day:
                job_func()
        
        return self.schedule.every().day.at(time_str).do(monthly_job)
    
    def _run_one_time_job(self, job_func: Callable, date_time_str: str) -> schedule.Job:
        """
        Schedule a one-time job at the specified date and time.
        
        Args:
            job_func: Function to run
            date_time_str: Date and time (e.g., "2023-01-01 08:00")
            
        Returns:
            Scheduled job
        """
        run_time = datetime.strptime(date_time_str, "%Y-%m-%d %H:%M")
        delay = (run_time - datetime.now()).total_seconds()
        
        if delay <= 0:
            logger.warning(f"One-time job scheduled in the past: {date_time_str}")
            return None
        
        return self.schedule.every(delay).seconds.do(job_func)
    
    def _validate_schedule_value(self, schedule_type: str, schedule_value: str) -> str:
        """
        Validate and prepare the schedule value based on the schedule type.
        
        Args:
            schedule_type: Type of schedule
            schedule_value: Value for the schedule
            
        Returns:
            Validated and prepared schedule value
        """
        if schedule_type == 'hourly':
            # Ensure minutes are valid
            minutes = [int(m.strip()) for m in schedule_value.split(',')]
            for minute in minutes:
                if minute < 0 or minute >= 60:
                    raise ValueError(f"Invalid minute value: {minute}")
            return ','.join(str(m) for m in minutes)
        
        elif schedule_type in ['daily', 'weekly', 'monthly']:
            # Ensure time is valid
            try:
                datetime.strptime(schedule_value.split(',')[-1], "%H:%M")
            except ValueError:
                raise ValueError(f"Invalid time value: {schedule_value}")
            return schedule_value
        
        elif schedule_type == 'one_time':
            # Ensure date and time are valid
            try:
                datetime.strptime(schedule_value, "%Y-%m-%d %H:%M")
            except ValueError:
                raise ValueError(f"Invalid date/time value: {schedule_value}")
            return schedule_value
        
        else:
            raise ValueError(f"Invalid schedule type: {schedule_type}")
    
    def _calculate_next_run(self, schedule_type: str, schedule_value: str) -> datetime:
        """
        Calculate the next run time for a job based on its schedule.
        
        Args:
            schedule_type: Type of schedule
            schedule_value: Value for the schedule
            
        Returns:
            Next run time as a datetime object
        """
        now = datetime.now()
        
        if schedule_type == 'hourly':
            minutes = [int(m.strip()) for m in schedule_value.split(',')]
            next_run = None
            
            for minute in minutes:
                run_time = now.replace(minute=minute, second=0, microsecond=0)
                if run_time > now:
                    next_run = run_time
                    break
            
            if not next_run:
                next_run = now.replace(hour=now.hour + 1, minute=minutes[0], second=0, microsecond=0)
            
            return next_run
        
        elif schedule_type == 'daily':
            run_time = datetime.strptime(schedule_value, "%H:%M").time()
            next_run = now.replace(hour=run_time.hour, minute=run_time.minute, second=0, microsecond=0)
            
            if next_run <= now:
                next_run += timedelta(days=1)
            
            return next_run
        
        elif schedule_type == 'weekly':
            day, time_str = schedule_value.split(',')
            run_time = datetime.strptime(time_str, "%H:%M").time()
            next_run = now.replace(hour=run_time.hour, minute=run_time.minute, second=0, microsecond=0)
            
            days_ahead = (getattr(schedule, day.lower()) - now.weekday() + 7) % 7
            if days_ahead == 0 and next_run <= now:
                days_ahead = 7
            
            next_run += timedelta(days=days_ahead)
            return next_run
        
        elif schedule_type == 'monthly':
            day, time_str = schedule_value.split(',')
            day = int(day)
            run_time = datetime.strptime(time_str, "%H:%M").time()
            next_run = now.replace(day=day, hour=run_time.hour, minute=run_time.minute, second=0, microsecond=0)
            
            if next_run <= now:
                next_month = now.month + 1 if now.month < 12 else 1
                next_year = now.year if now.month < 12 else now.year + 1
                next_run = next_run.replace(year=next_year, month=next_month)
            
            return next_run
        
        elif schedule_type == 'one_time':
            return datetime.strptime(schedule_value, "%Y-%m-%d %H:%M")
        
        else:
            raise ValueError(f"Invalid schedule type: {schedule_type}")
    
    def _execute_job(self, job_id: int, job_type: str, url: str, options: Dict[str, Any]):
        """
        Execute a scheduled job.
        
        Args:
            job_id: ID of the job
            job_type: Type of job (scrape_website or recursive_scrape)
            url: URL to scrape
            options: Options for the job
        """
        logger.info(f"Executing job {job_id}: {job_type} - {url}")
        
        # Update last run time
        self.db_manager.update_scheduled_job_run(job_id, last_run=datetime.now().isoformat())
        
        # Execute the job
        if job_type == 'scrape_website':
            self._execute_scrape_website(job_id, url, options)
        elif job_type == 'recursive_scrape':
            self._execute_recursive_scrape(job_id, url, options)
        else:
            logger.error(f"Invalid job type: {job_type}")
    
    def _execute_scrape_website(self, job_id: int, url: str, options: Dict[str, Any]):
        """
        Execute a website scraping job.
        
        Args:
            job_id: ID of the job
            url: URL to scrape
            options: Options for the job
        """
        logger.info(f"Scraping website: {url}")
        
        # Perform the scraping (placeholder for actual scraping logic)
        result = {
            'status': 'success',
            'data': f"Scraped data from {url}"
        }
        
        # Save result to database
        self.db_manager.save_scrape_result(job_id, result)
        
        logger.info(f"Scraping completed: {url}")
    
    def _execute_recursive_scrape(self, job_id: int, url: str, options: Dict[str, Any]):
        """
        Execute a recursive scraping job.
        
        Args:
            job_id: ID of the job
            url: URL to scrape
            options: Options for the job
        """
        logger.info(f"Recursively scraping: {url}")
        
        # Perform the recursive scraping (placeholder for actual scraping logic)
        result = {
            'status': 'success',
            'data': f"Recursively scraped data from {url}"
        }
        
        # Save result to database
        self.db_manager.save_scrape_result(job_id, result)
        
        logger.info(f"Recursive scraping completed: {url}")
    
    def _signal_handler(self, signum, frame):
        """Handle termination signals for graceful shutdown."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()