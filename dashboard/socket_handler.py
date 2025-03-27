"""
WebSocket handler for real-time communication with the dashboard.

Provides real-time updates on scraping progress, system metrics,
and worker status to the dashboard interface.
"""

import logging
import json
import time
import threading
from typing import Dict, Any
import psutil
from flask import Flask
from flask_socketio import SocketIO, emit

from scraping_project.distributed.task_manager import get_task_manager
from scraping_project.memory_manager import get_memory_manager

# Set up logging
logger = logging.getLogger(__name__)

# Initialize components
task_manager = get_task_manager()
memory_manager = get_memory_manager()

# Socket.IO instance
socketio = None

def init_socket_handler(app: Flask) -> SocketIO:
    """
    Initialize and return the Socket.IO handler.
    
    Args:
        app: Flask application to attach Socket.IO to
        
    Returns:
        SocketIO instance
    """
    global socketio
    
    # Create Socket.IO instance
    socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")
    
    # Set up event handlers
    @socketio.on('connect')
    def handle_connect():
        """Handle client connection."""
        logger.info("Client connected")
        # Send initial data
        _emit_system_metrics()
        _emit_active_tasks()
        _emit_worker_stats()
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnect."""
        logger.info("Client disconnected")
    
    @socketio.on('request_update')
    def handle_update_request(data):
        """
        Handle request for updated data.
        
        Args:
            data: Dictionary with the update type to request
        """
        update_type = data.get('type')
        
        if update_type == 'system_metrics':
            _emit_system_metrics()
        elif update_type == 'active_tasks':
            _emit_active_tasks()
        elif update_type == 'worker_stats':
            _emit_worker_stats()
        elif update_type == 'all':
            _emit_system_metrics()
            _emit_active_tasks()
            _emit_worker_stats()
    
    # Start background update threads
    _start_background_tasks()
    
    return socketio

def _emit_system_metrics():
    """Emit current system metrics."""
    if not socketio:
        return
        
    # Get memory usage
    memory_usage = memory_manager.get_memory_usage()
    
    # Get CPU usage
    cpu_percent = psutil.cpu_percent(interval=0.1)
    
    # Get disk usage
    from scraping_project.config import Config
    try:
        disk_usage = psutil.disk_usage(Config.SCRAPE_OUTPUT_DIR)
        disk_percent = disk_usage.percent
    except:
        disk_percent = 0
    
    # Prepare metrics data
    metrics = {
        'cpu': {
            'percent': cpu_percent
        },
        'memory': {
            'system_percent': memory_usage.get('system_percent', 0),
            'process_rss_mb': memory_usage.get('process_rss_mb', 0),
            'process_vms_mb': memory_usage.get('process_vms_mb', 0)
        },
        'disk': {
            'percent': disk_percent
        },
        'timestamp': int(time.time() * 1000)  # Milliseconds timestamp
    }
    
    # Emit to clients
    socketio.emit('system_metrics', metrics)

def _emit_active_tasks():
    """Emit data about active tasks."""
    if not socketio:
        return
        
    # Get active tasks
    active_tasks = task_manager.get_active_tasks()
    
    # Prepare tasks data
    tasks_data = {
        'active_tasks': active_tasks,
        'count': len(active_tasks),
        'timestamp': int(time.time() * 1000)
    }
    
    # Emit to clients
    socketio.emit('active_tasks', tasks_data)

def _emit_worker_stats():
    """Emit data about worker status."""
    if not socketio:
        return
        
    # Get worker stats
    worker_stats = task_manager.get_worker_stats()
    
    # Add timestamp
    worker_stats['timestamp'] = int(time.time() * 1000)
    
    # Emit to clients
    socketio.emit('worker_stats', worker_stats)

def _start_background_tasks():
    """Start background tasks for periodic updates."""
    if not socketio:
        return
    
    def metrics_updater():
        """Update system metrics every few seconds."""
        while True:
            _emit_system_metrics()
            time.sleep(3)  # Update every 3 seconds
    
    def tasks_updater():
        """Update task information every few seconds."""
        while True:
            _emit_active_tasks()
            time.sleep(2)  # Update every 2 seconds
    
    def worker_updater():
        """Update worker statistics every few seconds."""
        while True:
            _emit_worker_stats()
            time.sleep(5)  # Update every 5 seconds
    
    # Start the threads
    threading.Thread(target=metrics_updater, daemon=True).start()
    threading.Thread(target=tasks_updater, daemon=True).start()
    threading.Thread(target=worker_updater, daemon=True).start()

def emit_task_update(task_id: str, update_data: Dict[str, Any]):
    """
    Emit an update for a specific task.
    
    Args:
        task_id: ID of the task
        update_data: Data to emit
    """
    if not socketio:
        return
        
    # Add timestamp
    update_data['timestamp'] = int(time.time() * 1000)
    
    # Emit to clients
    socketio.emit(f'task_update_{task_id}', update_data)
    
    # Also emit to the general task channel
    socketio.emit('task_update', {
        'task_id': task_id,
        'data': update_data
    })
