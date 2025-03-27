"""
Worker module for running Celery workers.

This module configures and runs Celery workers for distributed scraping tasks.
"""

import os
import logging
import sys
import argparse
import socket
import platform
from datetime import datetime

from celery.bin import worker
from celery.signals import worker_ready, worker_shutdown

from .task_manager import celery_app
from ..config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(Config.LOG_DIR, f"worker_{datetime.now().strftime('%Y%m%d%H%M%S')}.log"))
    ]
)
logger = logging.getLogger(__name__)

@worker_ready.connect
def on_worker_ready(**kwargs):
    """Signal handler for when worker is ready."""
    hostname = socket.gethostname()
    logger.info(f"Worker ready on {hostname} - Python {platform.python_version()}")

@worker_shutdown.connect
def on_worker_shutdown(**kwargs):
    """Signal handler for when worker shuts down."""
    hostname = socket.gethostname()
    logger.info(f"Worker shutting down on {hostname}")

def start_worker(concurrency=1, queue='celery', loglevel='INFO'):
    """
    Start a Celery worker process.
    
    Args:
        concurrency: Number of worker processes
        queue: Queue to consume from
        loglevel: Logging level
    """
    # Get hostname for worker name
    hostname = socket.gethostname()
    worker_name = f"scrapy_worker_{hostname}_{os.getpid()}"
    
    logger.info(f"Starting worker {worker_name} with concurrency {concurrency}")
    
    # Setup worker arguments
    worker_args = [
        'worker',
        '--app=scraping_project.distributed.task_manager.celery_app',
        f'--concurrency={concurrency}',
        f'--hostname={worker_name}',
        f'--loglevel={loglevel}',
        f'--queues={queue}',
        '--without-gossip',      # Disable event gossip
        '--without-mingle',      # Don't synchronize with other workers at startup
        '--without-heartbeat',   # Don't send heartbeats
        '--pool=prefork',        # Use prefork process pool
    ]
    
    # Start the worker
    celery_worker = worker.worker(app=celery_app)
    celery_worker.run_from_argv(['celery'] + worker_args)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start a Scrapy Celery worker")
    parser.add_argument("--concurrency", type=int, default=1, help="Number of worker processes")
    parser.add_argument("--queue", type=str, default="celery", help="Queue to consume from")
    parser.add_argument("--loglevel", type=str, default="INFO", help="Logging level")
    
    args = parser.parse_args()
    
    start_worker(
        concurrency=args.concurrency,
        queue=args.queue,
        loglevel=args.loglevel
    )
