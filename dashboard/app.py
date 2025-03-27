"""
Scrapy Dashboard - Web UI for monitoring and controlling scraping jobs.

This module provides a Flask web application that serves as a central dashboard
for viewing scraping job status, results, and system metrics in real-time.
"""

import os
import logging
import json
import time
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, redirect, url_for
import plotly
import plotly.graph_objs as go
from typing import Dict, List, Any, Optional

from scraping_project.db_manager import DatabaseManager
from scraping_project.distributed.task_manager import get_task_manager
from scraping_project.memory_manager import get_memory_manager
from scraping_project.config import Config
from dashboard.socket_handler import init_socket_handler

# Initialize components
db_manager = DatabaseManager()
task_manager = get_task_manager()
memory_manager = get_memory_manager()

# Initialize Flask app
app = Flask(__name__, 
    static_folder='static',
    template_folder='templates'
)

# Configure app
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_key_for_scrapy_dashboard')
app.config['JSON_SORT_KEYS'] = False  # Preserve the order of keys in JSON responses

# Initialize WebSocket handler
socketio = init_socket_handler(app)

@app.route('/')
def home():
    """Dashboard home page."""
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    """Main dashboard view."""
    # Get summary stats for display
    active_tasks = task_manager.get_active_tasks()
    recent_tasks = task_manager.get_recent_tasks(limit=5)
    worker_stats = task_manager.get_worker_stats()
    
    memory_usage = memory_manager.get_memory_usage()
    
    stats = {
        'active_tasks': len(active_tasks),
        'queued_tasks': worker_stats.get('queued_tasks', 0),
        'workers': worker_stats.get('active_workers', 0),
        'tasks_today': db_manager.count_tasks_since(datetime.now() - timedelta(days=1)),
        'system_memory': f"{memory_usage.get('system_percent', 0)}%",
        'process_memory': f"{memory_usage.get('process_rss_mb', 0):.1f} MB"
    }
    
    return render_template(
        'dashboard.html',
        stats=stats,
        active_tasks=active_tasks,
        recent_tasks=recent_tasks
    )

@app.route('/tasks')
def tasks():
    """Task management view."""
    task_type = request.args.get('type', 'all')
    status = request.args.get('status', 'all')
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 20))
    
    # Get tasks from database based on filters
    if task_type == 'all' and status == 'all':
        tasks = db_manager.get_recent_distributed_tasks(limit=limit)
    elif task_type != 'all' and status == 'all':
        tasks = db_manager.get_tasks_by_type(task_type, limit=limit)
    elif task_type == 'all' and status != 'all':
        tasks = db_manager.get_distributed_tasks_by_status([status], limit=limit)
    else:
        tasks = db_manager.get_tasks_by_type_and_status(task_type, [status], limit=limit)
    
    # Get available task types for filter dropdown
    task_types = db_manager.get_distinct_task_types()
    
    return render_template(
        'tasks.html',
        tasks=tasks,
        task_types=task_types,
        current_type=task_type,
        current_status=status,
        page=page,
        limit=limit
    )

@app.route('/task/<task_id>')
def task_detail(task_id):
    """Task detail view."""
    task = task_manager.get_task_status(task_id)
    
    if not task:
        return render_template('error.html', message=f"Task {task_id} not found"), 404
    
    # For completed tasks, get the results
    result = None
    if task.get('status') == 'SUCCESS':
        result = task_manager.get_task_result(task_id)
    
    # Generate task timeline events
    timeline = _generate_task_timeline(task)
    
    return render_template(
        'task_detail.html',
        task=task,
        result=result,
        timeline=timeline
    )

@app.route('/workers')
def workers():
    """Worker management view."""
    worker_stats = task_manager.get_worker_stats()
    
    return render_template(
        'workers.html',
        worker_stats=worker_stats
    )

@app.route('/submit')
def submit_task():
    """Task submission form."""
    return render_template('submit_task.html')

@app.route('/analytics')
def analytics():
    """Analytics and data visualization view."""
    # Generate time-series plots of tasks per day
    dates, counts = db_manager.get_tasks_per_day(days=30)
    
    # Create tasks by status chart
    status_data = db_manager.get_task_counts_by_status()
    
    # Create tasks by type chart
    type_data = db_manager.get_task_counts_by_type()
    
    # Create success rate chart
    success_data = {
        'success': db_manager.count_tasks_by_status(['SUCCESS']),
        'failure': db_manager.count_tasks_by_status(['FAILURE', 'REVOKED', 'REJECTED'])
    }
    
    # Convert to Plotly JSON for the template
    tasks_plot = _create_time_series_plot(dates, counts, "Tasks per Day")
    status_plot = _create_pie_chart(status_data, "Tasks by Status")
    type_plot = _create_pie_chart(type_data, "Tasks by Type")
    success_plot = _create_pie_chart(success_data, "Success Rate")
    
    return render_template(
        'analytics.html',
        tasks_plot=json.dumps(tasks_plot, cls=plotly.utils.PlotlyJSONEncoder),
        status_plot=json.dumps(status_plot, cls=plotly.utils.PlotlyJSONEncoder),
        type_plot=json.dumps(type_plot, cls=plotly.utils.PlotlyJSONEncoder),
        success_plot=json.dumps(success_plot, cls=plotly.utils.PlotlyJSONEncoder)
    )

@app.route('/settings')
def settings():
    """System settings view."""
    # Get current configuration
    system_config = {
        'worker_concurrency': Config.WORKER_CONCURRENCY,
        'memory_warning_threshold': Config.MEMORY_WARNING_THRESHOLD,
        'memory_critical_threshold': Config.MEMORY_CRITICAL_THRESHOLD,
        'max_retries': Config.MAX_RETRIES,
        'retry_delay': Config.RETRY_DELAY,
        'scrape_output_dir': Config.SCRAPE_OUTPUT_DIR,
        'log_dir': Config.LOG_DIR,
        'database_path': Config.DATABASE_PATH,
        'default_user_agent': Config.DEFAULT_USER_AGENT
    }
    
    return render_template(
        'settings.html',
        config=system_config
    )

# API endpoints for dashboard operations

@app.route('/api/stats', methods=['GET'])
def api_stats():
    """Get system statistics."""
    active_tasks = task_manager.get_active_tasks()
    worker_stats = task_manager.get_worker_stats()
    memory_usage = memory_manager.get_memory_usage()
    
    stats = {
        'active_tasks': len(active_tasks),
        'queued_tasks': worker_stats.get('queued_tasks', 0),
        'workers': worker_stats.get('active_workers', 0),
        'tasks_today': db_manager.count_tasks_since(datetime.now() - timedelta(days=1)),
        'system_memory': memory_usage.get('system_percent', 0),
        'process_memory': memory_usage.get('process_rss_mb', 0)
    }
    
    return jsonify(stats)

@app.route('/api/memory_timeline', methods=['GET'])
def api_memory_timeline():
    """Get memory usage timeline."""
    # Get historical memory usage from memory manager
    history = memory_manager.get_usage_history(minutes=30)
    
    return jsonify(history)

@app.route('/api/task/<task_id>/cancel', methods=['POST'])
def api_cancel_task(task_id):
    """Cancel a task."""
    success = task_manager.cancel_task(task_id)
    
    if success:
        return jsonify({'status': 'success', 'message': f'Task {task_id} cancelled'})
    else:
        return jsonify({'status': 'error', 'message': 'Failed to cancel task'}), 400

@app.route('/api/task', methods=['POST'])
def api_submit_task():
    """Submit a new scraping task."""
    data = request.json
    
    if not data or 'url' not in data:
        return jsonify({'status': 'error', 'message': 'URL is required'}), 400
    
    url = data['url']
    task_type = data.get('type', 'scrape_website')
    options = data.get('options', {})
    
    if task_type == 'scrape_website':
        task_id = task_manager.submit_scrape_task(url, options)
    elif task_type == 'recursive_scrape':
        task_id = task_manager.submit_recursive_scrape_task(url, options)
    else:
        return jsonify({'status': 'error', 'message': f'Unknown task type: {task_type}'}), 400
    
    return jsonify({
        'status': 'success', 
        'task_id': task_id,
        'message': f'Task submitted successfully'
    })

# Helper functions

def _create_time_series_plot(x, y, title):
    """Create a time series plot."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=y, mode='lines+markers'))
    
    fig.update_layout(
        title=title,
        xaxis_title='Date',
        yaxis_title='Count',
        template='plotly_white'
    )
    
    return fig

def _create_pie_chart(data, title):
    """Create a pie chart."""
    labels = list(data.keys())
    values = list(data.values())
    
    fig = go.Figure(data=[go.Pie(labels=labels, values=values)])
    
    fig.update_layout(
        title=title,
        template='plotly_white'
    )
    
    return fig

def _generate_task_timeline(task):
    """Generate a timeline of task events."""
    timeline = []
    
    # Add creation time
    if 'created_at' in task:
        timeline.append({
            'time': task['created_at'],
            'event': 'Task created',
            'icon': 'plus-circle',
            'color': 'info'
        })
    
    # Add start time
    if 'started_at' in task and task['started_at']:
        timeline.append({
            'time': task['started_at'],
            'event': 'Task started',
            'icon': 'play-circle',
            'color': 'primary'
        })
    
    # Add status updates from logs
    task_logs = db_manager.get_task_logs(task['task_id']) if 'task_id' in task else []
    for log in task_logs:
        if log['log_level'] == 'INFO':
            timeline.append({
                'time': log['timestamp'],
                'event': log['message'],
                'icon': 'info-circle',
                'color': 'info'
            })
        elif log['log_level'] == 'WARNING':
            timeline.append({
                'time': log['timestamp'],
                'event': log['message'],
                'icon': 'exclamation-triangle',
                'color': 'warning'
            })
        elif log['log_level'] == 'ERROR':
            timeline.append({
                'time': log['timestamp'],
                'event': log['message'],
                'icon': 'exclamation-circle',
                'color': 'danger'
            })
    
    # Add completion time
    if 'completed_at' in task and task['completed_at']:
        status = task.get('status', 'UNKNOWN')
        if status == 'SUCCESS':
            timeline.append({
                'time': task['completed_at'],
                'event': 'Task completed successfully',
                'icon': 'check-circle',
                'color': 'success'
            })
        elif status == 'FAILURE':
            timeline.append({
                'time': task['completed_at'],
                'event': 'Task failed',
                'icon': 'times-circle',
                'color': 'danger'
            })
        elif status == 'REVOKED':
            timeline.append({
                'time': task['completed_at'],
                'event': 'Task was cancelled',
                'icon': 'ban',
                'color': 'warning'
            })
        else:
            timeline.append({
                'time': task['completed_at'],
                'event': f'Task ended with status: {status}',
                'icon': 'flag-checkered',
                'color': 'secondary'
            })
    
    # Sort by time
    timeline.sort(key=lambda x: x['time'])
    
    return timeline

if __name__ == '__main__':
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Start the Socket.IO server
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)
