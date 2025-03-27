"""
Plugin system for extending Scrapy functionality.

This module provides a flexible plugin architecture that allows adding
custom processors, scrapers, exporters, and transformers.
"""

import os
import sys
import importlib
import importlib.util
import inspect
import logging
import json
import pkgutil
from typing import Dict, List, Any, Optional, Callable, Type, Set, Tuple
from enum import Enum, auto

from scraping_project.config import Config

# Set up logging
logger = logging.getLogger(__name__)

# Plugin interface classes
class PluginType(Enum):
    """Enum defining the types of plugins supported."""
    PROCESSOR = auto()  # Content processors
    EXPORTER = auto()  # Data exporters
    SCRAPER = auto()  # Custom scrapers
    TRANSFORMER = auto()  # Data transformers
    MIDDLEWARE = auto()  # Request/response middleware
    NOTIFICATION = auto()  # Notification systems
    STORAGE = auto()  # Storage backends

class ScrapyPlugin:
    """Base class for all Scrapy plugins."""
    
    # Class attributes that should be defined by subclasses
    plugin_name = "base_plugin"
    plugin_type = None  # Should be a PluginType enum value
    plugin_description = "Base plugin class"
    plugin_version = "0.1.0"
    plugin_author = "Unknown"
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the plugin.
        
        Args:
            config: Optional configuration for the plugin
        """
        self.config = config or {}
        self.is_enabled = True
    
    def validate