import os
import sqlite3
import json
from datetime import datetime
import logging
import uuid
from typing import List, Dict, Any, Optional, Union, Tuple

class DatabaseManager:
    """
    Database manager for storing and retrieving scraping results.
    Uses SQLite for simplicity, but designed to be extendable to other databases.
    """
    
    def __init__(self, db_path: str = None):
        """Initialize database connection and create tables if they don't exist."""
        from config import Config
        
        if db_path is None:
            self.db_path = os.path.join(Config.BASE_DIR, 'scrapy_results.db')
        else:
            self.db_path = db_path
            
        self.logger = logging.getLogger(__name__)
        self._init_db()
    
    def _init_db(self) -> None:
        """Create necessary tables if they don't exist."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Create scraping_jobs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scraping_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    status TEXT NOT NULL,
                    job_type TEXT NOT NULL,
                    follow_links INTEGER,
                    max_pages INTEGER,
                    duration REAL,
                    metadata TEXT,
                    user_id INTEGER
                )
            ''')
            
            # Create scraped_pages table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scraped_pages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id INTEGER NOT NULL,
                    url TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    title TEXT,
                    content_hash TEXT,
                    word_count INTEGER,
                    screenshot_path TEXT,
                    html_path TEXT,
                    analysis_path TEXT,
                    report_path TEXT,
                    FOREIGN KEY (job_id) REFERENCES scraping_jobs (id)
                )
            ''')
            
            # Create users table for authentication
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    email TEXT UNIQUE,
                    created_at TEXT NOT NULL,
                    last_login TEXT,
                    is_admin INTEGER DEFAULT 0
                )
            ''')
            
            # Create scheduled_jobs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scheduled_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    schedule_type TEXT NOT NULL,
                    schedule_value TEXT NOT NULL,
                    follow_links INTEGER,
                    max_pages INTEGER,
                    last_run TEXT,
                    next_run TEXT,
                    user_id INTEGER,
                    is_active INTEGER DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            # Add distributed task table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS distributed_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT UNIQUE,
                    task_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    metadata TEXT,
                    result_data TEXT,
                    user_id INTEGER,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            # Add task_logs table for detailed task execution logs
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS task_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    log_level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES distributed_tasks (task_id)
                )
            ''')
            
            # Add worker_stats table to track worker performance
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS worker_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    worker_id TEXT NOT NULL,
                    hostname TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    cpu_percent REAL,
                    memory_percent REAL,
                    task_count INTEGER,
                    status TEXT
                )
            ''')
            
            conn.commit()
            self.logger.info("Database initialized successfully")
            
        except sqlite3.Error as e:
            self.logger.error(f"Database initialization error: {e}")
            raise
        finally:
            conn.close()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # This enables column access by name
            return conn
        except sqlite3.Error as e:
            self.logger.error(f"Database connection error: {e}")
            raise
    
    def save_scraping_job(self, url: str, job_type: str, status: str, 
                         follow_links: bool = False, max_pages: int = 10, 
                         duration: float = None, metadata: Dict = None, 
                         user_id: int = None) -> int:
        """Save a scraping job to the database and return its ID."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            timestamp = datetime.now().isoformat()
            
            metadata_json = json.dumps(metadata) if metadata else None
            
            cursor.execute('''
                INSERT INTO scraping_jobs 
                (url, timestamp, status, job_type, follow_links, max_pages, duration, metadata, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (url, timestamp, status, job_type, int(follow_links), max_pages, 
                  duration, metadata_json, user_id))
            
            conn.commit()
            job_id = cursor.lastrowid
            self.logger.info(f"Saved scraping job with ID: {job_id}")
            return job_id
            
        except sqlite3.Error as e:
            conn.rollback()
            self.logger.error(f"Error saving scraping job: {e}")
            raise
        finally:
            conn.close()
    
    def save_scraped_page(self, job_id: int, url: str, title: str = None, 
                         word_count: int = 0, screenshot_path: str = None, 
                         html_path: str = None, analysis_path: str = None, 
                         report_path: str = None) -> int:
        """Save a scraped page to the database and return its ID."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            timestamp = datetime.now().isoformat()
            
            # Simple content hash based on URL and timestamp
            import hashlib
            content_hash = hashlib.md5(f"{url}_{timestamp}".encode()).hexdigest()
            
            cursor.execute('''
                INSERT INTO scraped_pages 
                (job_id, url, timestamp, title, content_hash, word_count, 
                screenshot_path, html_path, analysis_path, report_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (job_id, url, timestamp, title, content_hash, word_count, 
                  screenshot_path, html_path, analysis_path, report_path))
            
            conn.commit()
            page_id = cursor.lastrowid
            self.logger.info(f"Saved scraped page with ID: {page_id}")
            return page_id
            
        except sqlite3.Error as e:
            conn.rollback()
            self.logger.error(f"Error saving scraped page: {e}")
            raise
        finally:
            conn.close()
    
    def get_scraping_job(self, job_id: int) -> Dict:
        """Get a scraping job by its ID."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM scraping_jobs WHERE id = ?
            ''', (job_id,))
            
            row = cursor.fetchone()
            if row:
                job = dict(row)
                if job.get('metadata'):
                    job['metadata'] = json.loads(job['metadata'])
                return job
            return None
            
        except sqlite3.Error as e:
            self.logger.error(f"Error retrieving scraping job: {e}")
            raise
        finally:
            conn.close()
    
    def get_recent_jobs(self, limit: int = 10, user_id: int = None) -> List[Dict]:
        """Get recent scraping jobs, optionally filtered by user ID."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            query = '''
                SELECT * FROM scraping_jobs 
                ORDER BY timestamp DESC
                LIMIT ?
            '''
            params = (limit,)
            
            if user_id is not None:
                query = '''
                    SELECT * FROM scraping_jobs 
                    WHERE user_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                '''
                params = (user_id, limit)
            
            cursor.execute(query, params)
            
            jobs = []
            for row in cursor.fetchall():
                job = dict(row)
                if job.get('metadata'):
                    try:
                        job['metadata'] = json.loads(job['metadata'])
                    except json.JSONDecodeError:
                        job['metadata'] = {}
                jobs.append(job)
            return jobs
            
        except sqlite3.Error as e:
            self.logger.error(f"Error retrieving recent jobs: {e}")
            raise
        finally:
            conn.close()
    
    def get_pages_for_job(self, job_id: int) -> List[Dict]:
        """Get all pages associated with a scraping job."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM scraped_pages 
                WHERE job_id = ?
                ORDER BY timestamp
            ''', (job_id,))
            
            pages = [dict(row) for row in cursor.fetchall()]
            return pages
            
        except sqlite3.Error as e:
            self.logger.error(f"Error retrieving pages for job: {e}")
            raise
        finally:
            conn.close()
    
    def search_scraped_content(self, query: str) -> List[Dict]:
        """Search for scraped content matching the query."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT p.*, j.url as job_url FROM scraped_pages p
                JOIN scraping_jobs j ON p.job_id = j.id
                WHERE p.title LIKE ? OR j.url LIKE ?
                ORDER BY p.timestamp DESC
            ''', (f'%{query}%', f'%{query}%'))
            
            results = [dict(row) for row in cursor.fetchall()]
            return results
            
        except sqlite3.Error as e:
            self.logger.error(f"Error searching scraped content: {e}")
            raise
        finally:
            conn.close()
    
    def add_user(self, username: str, password_hash: str, email: str = None, 
                is_admin: bool = False) -> int:
        """Add a new user to the database."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            created_at = datetime.now().isoformat()
            
            cursor.execute('''
                INSERT INTO users 
                (username, password_hash, email, created_at, is_admin)
                VALUES (?, ?, ?, ?, ?)
            ''', (username, password_hash, email, created_at, int(is_admin)))
            
            conn.commit()
            user_id = cursor.lastrowid
            self.logger.info(f"Added user with ID: {user_id}")
            return user_id
            
        except sqlite3.Error as e:
            conn.rollback()
            self.logger.error(f"Error adding user: {e}")
            raise
        finally:
            conn.close()
    
    def get_user_by_username(self, username: str) -> Dict:
        """Get a user by username."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM users WHERE username = ?
            ''', (username,))
            
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
            
        except sqlite3.Error as e:
            self.logger.error(f"Error retrieving user: {e}")
            raise
        finally:
            conn.close()
    
    def update_user_last_login(self, user_id: int) -> None:
        """Update a user's last login timestamp."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            last_login = datetime.now().isoformat()
            
            cursor.execute('''
                UPDATE users SET last_login = ? WHERE id = ?
            ''', (last_login, user_id))
            
            conn.commit()
            
        except sqlite3.Error as e:
            conn.rollback()
            self.logger.error(f"Error updating user last login: {e}")
            raise
        finally:
            conn.close()
    
    def add_scheduled_job(self, job_name: str, url: str, schedule_type: str, 
                         schedule_value: str, follow_links: bool = False, 
                         max_pages: int = 10, user_id: int = None) -> int:
        """Add a scheduled scraping job."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO scheduled_jobs 
                (job_name, url, schedule_type, schedule_value, follow_links, max_pages, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (job_name, url, schedule_type, schedule_value, 
                  int(follow_links), max_pages, user_id))
            
            conn.commit()
            job_id = cursor.lastrowid
            self.logger.info(f"Added scheduled job with ID: {job_id}")
            return job_id
            
        except sqlite3.Error as e:
            conn.rollback()
            self.logger.error(f"Error adding scheduled job: {e}")
            raise
        finally:
            conn.close()
    
    def update_scheduled_job_run(self, job_id: int, last_run: str, next_run: str) -> None:
        """Update the last run and next run time of a scheduled job."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE scheduled_jobs 
                SET last_run = ?, next_run = ?
                WHERE id = ?
            ''', (last_run, next_run, job_id))
            
            conn.commit()
            
        except sqlite3.Error as e:
            conn.rollback()
            self.logger.error(f"Error updating scheduled job run: {e}")
            raise
        finally:
            conn.close()
    
    def get_pending_scheduled_jobs(self) -> List[Dict]:
        """Get scheduled jobs that are due to run."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            
            cursor.execute('''
                SELECT * FROM scheduled_jobs 
                WHERE next_run <= ? AND is_active = 1
                ORDER BY next_run
            ''', (now,))
            
            jobs = [dict(row) for row in cursor.fetchall()]
            return jobs
            
        except sqlite3.Error as e:
            self.logger.error(f"Error retrieving pending scheduled jobs: {e}")
            raise
        finally:
            conn.close()

    def export_job_data(self, job_id: int, format_type: str = 'json') -> str:
        """Export job data in the specified format (json, csv)."""
        job = self.get_scraping_job(job_id)
        if not job:
            raise ValueError(f"Job with ID {job_id} not found")
            
        pages = self.get_pages_for_job(job_id)
        
        export_data = {
            "job": job,
            "pages": pages
        }
        
        if format_type.lower() == 'json':
            return json.dumps(export_data, indent=2)
        elif format_type.lower() == 'csv':
            # Simple CSV export
            import csv
            from io import StringIO
            
            output = StringIO()
            writer = csv.writer(output)
            
            # Write headers
            writer.writerow(["Page ID", "URL", "Title", "Word Count", "Timestamp"])
            
            # Write data rows
            for page in pages:
                writer.writerow([
                    page.get("id", ""),
                    page.get("url", ""),
                    page.get("title", ""),
                    page.get("word_count", ""),
                    page.get("timestamp", "")
                ])
                
            return output.getvalue()
        else:
            raise ValueError(f"Unsupported export format: {format_type}")

    # Add these new methods for distributed task management
    
    def create_distributed_task(
        self, 
        task_type: str, 
        status: str = "PENDING", 
        metadata: Optional[Dict] = None, 
        user_id: Optional[int] = None
    ) -> str:
        """
        Create a new distributed task record.
        
        Args:
            task_type: Type of the task
            status: Initial status
            metadata: Optional metadata
            user_id: Optional user ID
            
        Returns:
            Task ID
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            created_at = datetime.now().isoformat()
            task_id = str(uuid.uuid4())
            
            metadata_json = json.dumps(metadata) if metadata else None
            
            cursor.execute('''
                INSERT INTO distributed_tasks 
                (task_id, task_type, status, created_at, metadata, user_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (task_id, task_type, status, created_at, metadata_json, user_id))
            
            conn.commit()
            record_id = cursor.lastrowid
            self.logger.info(f"Created distributed task with ID: {task_id}")
            return str(record_id)
            
        except sqlite3.Error as e:
            conn.rollback()
            self.logger.error(f"Error creating distributed task: {e}")
            raise
        finally:
            conn.close()
    
    def update_distributed_task(
        self,
        task_id: str,
        status: Optional[str] = None,
        progress: Optional[int] = None,
        metadata: Optional[Dict] = None,
        result_data: Optional[Dict] = None,
        started_at: Optional[str] = None,
        completed_at: Optional[str] = None
    ) -> bool:
        """
        Update a distributed task record.
        
        Args:
            task_id: ID of the task to update
            status: New status (if provided)
            progress: New progress percentage (if provided)
            metadata: Updated metadata (if provided)
            result_data: Task result data (if provided)
            started_at: Task start timestamp (if provided)
            completed_at: Task completion timestamp (if provided)
            
        Returns:
            True if update was successful
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Build the update statement and parameters dynamically
            update_parts = []
            update_values = []
            
            if status is not None:
                update_parts.append("status = ?")
                update_values.append(status)
                
            if progress is not None:
                update_parts.append("progress = ?")
                update_values.append(progress)
                
            if metadata is not None:
                update_parts.append("metadata = ?")
                update_values.append(json.dumps(metadata))
                
            if result_data is not None:
                update_parts.append("result_data = ?")
                update_values.append(json.dumps(result_data))
                
            if started_at is not None:
                update_parts.append("started_at = ?")
                update_values.append(started_at)
                
            if completed_at is not None:
                update_parts.append("completed_at = ?")
                update_values.append(completed_at)
            
            # If no updates were provided, return early
            if not update_parts:
                return True
                
            # Build the full query
            query = f"UPDATE distributed_tasks SET {', '.join(update_parts)} WHERE task_id = ?"
            update_values.append(task_id)
            
            # Execute the update
            cursor.execute(query, update_values)
            conn.commit()
            
            # Check if the update was successful
            return cursor.rowcount > 0
            
        except sqlite3.Error as e:
            conn.rollback()
            self.logger.error(f"Error updating distributed task: {e}")
            raise
        finally:
            conn.close()
    
    def get_distributed_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a distributed task by ID.
        
        Args:
            task_id: ID of the task
            
        Returns:
            Task data or None if not found
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM distributed_tasks WHERE task_id = ?
            ''', (task_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
                
            task = dict(row)
            
            # Parse JSON fields
            if task.get('metadata'):
                try:
                    task['metadata'] = json.loads(task['metadata'])
                except json.JSONDecodeError:
                    task['metadata'] = {}
                    
            if task.get('result_data'):
                try:
                    task['result_data'] = json.loads(task['result_data'])
                except json.JSONDecodeError:
                    task['result_data'] = {}
            
            return task
            
        except sqlite3.Error as e:
            self.logger.error(f"Error retrieving distributed task: {e}")
            raise
        finally:
            conn.close()
    
    def get_distributed_tasks_by_status(self, statuses: List[str]) -> List[Dict[str, Any]]:
        """
        Get distributed tasks by status.
        
        Args:
            statuses: List of status values to match
            
        Returns:
            List of matching tasks
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Create placeholders for statuses
            placeholders = ', '.join(['?'] * len(statuses))
            
            cursor.execute(f'''
                SELECT * FROM distributed_tasks 
                WHERE status IN ({placeholders})
                ORDER BY created_at DESC
            ''', statuses)
            
            tasks = []
            for row in cursor.fetchall():
                task = dict(row)
                
                # Parse JSON fields
                if task.get('metadata'):
                    try:
                        task['metadata'] = json.loads(task['metadata'])
                    except json.JSONDecodeError:
                        task['metadata'] = {}
                        
                if task.get('result_data'):
                    try:
                        task['result_data'] = json.loads(task['result_data'])
                    except json.JSONDecodeError:
                        task['result_data'] = {}
                
                tasks.append(task)
                
            return tasks
            
        except sqlite3.Error as e:
            self.logger.error(f"Error retrieving distributed tasks by status: {e}")
            raise
        finally:
            conn.close()
    
    def get_recent_distributed_tasks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent distributed tasks.
        
        Args:
            limit: Maximum number of tasks to retrieve
            
        Returns:
            List of recent tasks
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM distributed_tasks 
                ORDER BY created_at DESC
                LIMIT ?
            ''', (limit,))
            
            tasks = []
            for row in cursor.fetchall():
                task = dict(row)
                
                # Parse JSON fields
                if task.get('metadata'):
                    try:
                        task['metadata'] = json.loads(task['metadata'])
                    except json.JSONDecodeError:
                        task['metadata'] = {}
                        
                if task.get('result_data'):
                    try:
                        task['result_data'] = json.loads(task['result_data'])
                    except json.JSONDecodeError:
                        task['result_data'] = {}
                
                tasks.append(task)
                
            return tasks
            
        except sqlite3.Error as e:
            self.logger.error(f"Error retrieving recent distributed tasks: {e}")
            raise
        finally:
            conn.close()
