"""
WebSocket server for real-time scraping job monitoring.

Provides real-time updates on scraping progress, worker status,
and system metrics to connected dashboard clients.
"""

import os
import json
import asyncio
import logging
import time
import threading
from typing import Dict, List, Set, Any, Optional
import datetime
import psutil

import websockets
from websockets.server import serve

from ..db_manager import DatabaseManager
from ..distributed.task_manager import get_task_manager
from ..memory_manager import get_memory_manager

# Initialize components
db_manager = DatabaseManager()
task_manager = get_task_manager()
memory_manager = get_memory_manager()

# Set up logging
logger = logging.getLogger(__name__)

class ScrapyWebSocketServer:
    """
    WebSocket server for real-time monitoring of scraping tasks.
    
    Provides functionality to:
    - Send real-time job progress updates
    - Stream system metrics
    - Send worker status updates
    - Handle client commands
    """
    
    def __init__(self, host: str = 'localhost', port: int = 8765):
        """
        Initialize the WebSocket server.
        
        Args:
            host: Hostname to bind the server to
            port: Port to listen on
        """
        self.host = host
        self.port = port
        self.connected_clients: Set[websockets.WebSocketServerProtocol] = set()
        self.active_tasks: Dict[str, Dict] = {}  # task_id -> task_info
        self.running = False
        self.server = None
        
        # Background tasks
        self.metrics_task = None
        self.task_monitor_task = None
        
        logger.info(f"WebSocket server initialized at ws://{host}:{port}")
    
    async def start(self):
        """Start the WebSocket server."""
        if self.running:
            logger.warning("WebSocket server already running")
            return
        
        self.running = True
        
        # Start the server
        self.server = await serve(
            self._handle_client,
            self.host, 
            self.port,
            ping_interval=30,  # Send ping every 30 seconds
            ping_timeout=10     # Wait 10 seconds for pong
        )
        
        # Start background tasks
        self.metrics_task = asyncio.create_task(self._metrics_reporter())
        self.task_monitor_task = asyncio.create_task(self._monitor_active_tasks())
        
        logger.info(f"WebSocket server started at ws://{self.host}:{self.port}")
        
        # Keep server running
        try:
            await self.server.wait_closed()
        finally:
            self.running = False
            if self.metrics_task:
                self.metrics_task.cancel()
            if self.task_monitor_task:
                self.task_monitor_task.cancel()
    
    async def stop(self):
        """Stop the WebSocket server."""
        if not self.running:
            return
            
        logger.info("Stopping WebSocket server...")
        
        # Cancel background tasks
        if self.metrics_task:
            self.metrics_task.cancel()
        
        if self.task_monitor_task:
            self.task_monitor_task.cancel()
        
        # Close all client connections
        if self.connected_clients:
            close_message = json.dumps({"type": "server_shutdown", "message": "Server shutting down"})
            await asyncio.gather(
                *(client.send(close_message) for client in self.connected_clients),
                return_exceptions=True
            )
            self.connected_clients.clear()
        
        # Close server
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        self.running = False
        logger.info("WebSocket server stopped")
    
    async def _handle_client(self, websocket: websockets.WebSocketServerProtocol, path: str):
        """
        Handle a client connection.
        
        Args:
            websocket: WebSocket connection
            path: Connection path
        """
        # Register client
        self.connected_clients.add(websocket)
        client_id = id(websocket)
        remote = websocket.remote_address
        logger.info(f"Client connected: {remote} (ID: {client_id})")
        
        try:
            # Send initial data to the client
            await self._send_initial_data(websocket)
            
            # Handle client messages
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self._process_client_message(websocket, data)
                except json.JSONDecodeError:
                    logger.warning(f"Received invalid JSON from client {client_id}")
                    await websocket.send(json.dumps({
                        "type": "error", 
                        "message": "Invalid JSON format"
                    }))
                except Exception as e:
                    logger.error(f"Error processing message from client {client_id}: {e}")
                    await websocket.send(json.dumps({
                        "type": "error", 
                        "message": f"Error processing request: {str(e)}"
                    }))
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client {client_id} disconnected normally")
        except Exception as e:
            logger.error(f"Error handling client {client_id}: {e}")
        finally:
            # Unregister client
            self.connected_clients.discard(websocket)
            logger.info(f"Client {client_id} connection closed")
    
    async def _send_initial_data(self, websocket: websockets.WebSocketServerProtocol):
        """
        Send initial data to a newly connected client.
        
        Args:
            websocket: Client websocket connection
        """
        # Send active tasks
        active_tasks = task_manager.get_active_tasks()
        await websocket.send(json.dumps({
            "type": "active_tasks_update",
            "tasks": active_tasks,
            "count": len(active_tasks)
        }))
        
        # Send system metrics
        metrics = self._get_system_metrics()
        await websocket.send(json.dumps({
            "type": "system_metrics",
            "metrics": metrics
        }))
        
        # Send worker stats
        worker_stats = task_manager.get_worker_stats()
        await websocket.send(json.dumps({
            "type": "worker_stats",
            "stats": worker_stats
        }))
    
    async def _process_client_message(
        self, 
        websocket: websockets.WebSocketServerProtocol, 
        data: Dict[str, Any]
    ):
        """
        Process a message from a client.
        
        Args:
            websocket: Client websocket
            data: Parsed message data
        """
        message_type = data.get("type")
        
        if message_type == "ping":
            # Respond to ping with pong
            await websocket.send(json.dumps({"type": "pong", "timestamp": time.time()}))
            
        elif message_type == "get_task":
            # Retrieve task details
            task_id = data.get("task_id")
            if task_id:
                task_details = task_manager.get_task_status(task_id)
                await websocket.send(json.dumps({
                    "type": "task_details",
                    "task": task_details
                }))
            else:
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": "Missing task_id parameter"
                }))
                
        elif message_type == "cancel_task":
            # Cancel a task
            task_id = data.get("task_id")
            if task_id:
                success = task_manager.cancel_task(task_id)
                await websocket.send(json.dumps({
                    "type": "task_cancelled",
                    "task_id": task_id,
                    "success": success
                }))
            else:
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": "Missing task_id parameter"
                }))
                
        elif message_type == "get_recent_tasks":
            # Get recent tasks
            limit = int(data.get("limit", 10))
            recent_tasks = task_manager.get_recent_tasks(limit=limit)
            await websocket.send(json.dumps({
                "type": "recent_tasks",
                "tasks": recent_tasks,
                "count": len(recent_tasks)
            }))
            
        else:
            # Unknown message type
            await websocket.send(json.dumps({
                "type": "error",
                "message": f"Unknown message type: {message_type}"
            }))
    
    async def broadcast(self, message: Dict[str, Any]):
        """
        Broadcast a message to all connected clients.
        
        Args:
            message: Message to broadcast
        """
        if not self.connected_clients:
            return
            
        message_json = json.dumps(message)
        await asyncio.gather(
            *(client.send(message_json) for client in self.connected_clients),
            return_exceptions=True
        )
    
    async def _metrics_reporter(self):
        """Background task to periodically send system metrics to clients."""
        try:
            while self.running:
                if self.connected_clients:
                    metrics = self._get_system_metrics()
                    await self.broadcast({
                        "type": "system_metrics",
                        "metrics": metrics
                    })
                
                # Wait before sending next update
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            # Task was cancelled - exit cleanly
            pass
        except Exception as e:
            logger.error(f"Error in metrics reporter: {e}")
    
    async def _monitor_active_tasks(self):
        """Background task to monitor and report task status changes."""
        try:
            while self.running:
                # Get current active tasks
                active_tasks = task_manager.get_active_tasks()
                active_task_ids = {task["task_id"] for task in active_tasks}
                
                # Check for completed tasks
                completed_tasks = []
                for task_id in list(self.active_tasks.keys()):
                    if task_id not in active_task_ids:
                        # Task is no longer active - it completed
                        completed_task = task_manager.get_task_status(task_id)
                        if completed_task:
                            completed_tasks.append(completed_task)
                            del self.active_tasks[task_id]
                
                # Update active tasks dict
                for task in active_tasks:
                    task_id = task["task_id"]
                    if task_id not in self.active_tasks:
                        self.active_tasks[task_id] = task
                    else:
                        # Update existing task if status or progress changed
                        old_task = self.active_tasks[task_id]
                        if (old_task["status"] != task["status"] or 
                            old_task.get("progress", 0) != task.get("progress", 0)):
                            self.active_tasks[task_id] = task
                
                # Broadcast updates to clients if there are changes
                if self.connected_clients:
                    if active_tasks:
                        await self.broadcast({
                            "type": "active_tasks_update",
                            "tasks": active_tasks,
                            "count": len(active_tasks)
                        })
                    
                    if completed_tasks:
                        await self.broadcast({
                            "type": "completed_tasks_update",
                            "tasks": completed_tasks,
                            "count": len(completed_tasks)
                        })
                
                # Update worker stats periodically
                worker_stats = task_manager.get_worker_stats()
                if self.connected_clients:
                    await self.broadcast({
                        "type": "worker_stats",
                        "stats": worker_stats
                    })
                
                # Wait before checking again
                await asyncio.sleep(2)
        except asyncio.CancelledError:
            # Task was cancelled - exit cleanly
            pass
        except Exception as e:
            logger.error(f"Error in active task monitor: {e}")
    
    def _get_system_metrics(self) -> Dict[str, Any]:
        """
        Get current system metrics.
        
        Returns:
            Dictionary with system metrics
        """
        # Get CPU and memory usage
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        
        # Get disk usage of output directory
        from ..config import Config
        try:
            disk_usage = psutil.disk_usage(Config.SCRAPE_OUTPUT_DIR)
            disk_percent = disk_usage.percent
            disk_free_gb = disk_usage.free / (1024 * 1024 * 1024)
        except:
            disk_percent = 0
            disk_free_gb = 0
        
        #