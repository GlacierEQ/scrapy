"""
Scrapy Command Line Interface

A comprehensive CLI tool for running scrapy operations and managing scraping tasks.
"""

import os
import sys
import time
import json
import logging
import argparse
import configparser
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from datetime import datetime

# Add parent directory to path for imports
script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(script_dir)
sys.path.insert(0, root_dir)

# Import scrapy modules
from scraping_project.general_webscraper import WebpageScraper
from scraping_project.adaptive_scraper import AdaptiveScraper
from scraping_project.recursive_scraper import RecursiveScraper
from scraping_project.db_manager import DatabaseManager
from scraping_project.memory_manager import get_memory_manager
from scraping_project.config import Config
from scraping_project.distributed.task_manager import get_task_manager
from visualization.data_visualizer import ScrapyVisualizer

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Log to console
    ]
)
logger = logging.getLogger('scrapy-cli')

# Initialize key components
db_manager = DatabaseManager()
task_manager = get_task_manager()
memory_manager = get_memory_manager()

class ScrapyCLI:
    """
    Command-line interface for Scrapy operations.
    
    This class handles command-line arguments and executes the
    appropriate functions based on the user's input.
    """
    
    def __init__(self):
        """Initialize the CLI tool."""
        self.parser = self._create_parser()
        self.config = self._load_config()
        self.output_dir = self.config.get('output_dir', Config.SCRAPE_OUTPUT_DIR)
    
    def _create_parser(self) -> argparse.ArgumentParser:
        """
        Create the argument parser with all available commands.
        
        Returns:
            Configured argument parser
        """
        parser = argparse.ArgumentParser(
            prog='scrapy',
            description='Command line tool for Scrapy operations',
            epilog='For more information, visit: https://github.com/user/scrapy'
        )
        
        # Create subparsers for different commands
        subparsers = parser.add_subparsers(dest='command', help='Command to execute')
        
        # Scrape command
        scrape_parser = subparsers.add_parser('scrape', help='Scrape a URL')
        scrape_parser.add_argument('url', help='URL to scrape')
        scrape_parser.add_argument('--output', '-o', help='Output file path')
        scrape_parser.add_argument('--format', '-f', choices=['json', 'csv', 'xlsx'], default='json',
                                  help='Output format (default: json)')
        scrape_parser.add_argument('--screenshot', '-s', action='store_true', help='Save screenshot')
        scrape_parser.add_argument('--no-text', action='store_true', help='Skip text analysis')
        scrape_parser.add_argument('--user-agent', help='Custom user agent')
        scrape_parser.add_argument('--timeout', type=int, default=30, help='Request timeout in seconds')
        
        # Recursive scrape command
        recursive_parser = subparsers.add_parser('recursive', help='Recursively scrape a website')
        recursive_parser.add_argument('url', help='Starting URL')
        recursive_parser.add_argument('--output', '-o', help='Output file path')
        recursive_parser.add_argument('--format', '-f', choices=['json', 'csv', 'xlsx'], default='json',
                                     help='Output format (default: json)')
        recursive_parser.add_argument('--depth', '-d', type=int, default=2, help='Maximum crawl depth')
        recursive_parser.add_argument('--limit', '-l', type=int, default=50, help='Maximum pages to scrape')
        recursive_parser.add_argument('--same-domain', action='store_true', help='Stay on the same domain')
        recursive_parser.add_argument('--include', action='append', help='URL patterns to include')
        recursive_parser.add_argument('--exclude', action='append', help='URL patterns to exclude')
        recursive_parser.add_argument('--respect-robots', action='store_true', help='Respect robots.txt')
        recursive_parser.add_argument('--delay', type=float, default=0.5, help='Seconds between requests')
        
        # Adaptive scrape command
        adaptive_parser = subparsers.add_parser('adaptive', help='Use adaptive scraping')
        adaptive_parser.add_argument('url', help='URL to scrape')
        adaptive_parser.add_argument('--output', '-o', help='Output file path')
        adaptive_parser.add_argument('--format', '-f', choices=['json', 'csv', 'xlsx'], default='json',
                                    help='Output format (default: json)')
        adaptive_parser.add_argument('--type', choices=['auto', 'product', 'article', 'list', 'table'], 
                                   default='auto', help='Type of content to extract (default: auto)')
        adaptive_parser.add_argument('--ai', action='store_true', help='Use AI for extraction')
        adaptive_parser.add_argument('--screenshot', '-s', action='store_true', help='Save screenshot')
        
        # Task management commands
        tasks_parser = subparsers.add_parser('tasks', help='Manage scraping tasks')
        tasks_subparsers = tasks_parser.add_subparsers(dest='task_command', help='Task command')
        
        # List tasks command
        list_tasks_parser = tasks_subparsers.add_parser('list', help='List tasks')
        list_tasks_parser.add_argument('--status', choices=['in_progress', 'success', 'error', 'all'],
                                     default='all', help='Filter by status')
        list_tasks_parser.add_argument('--limit', type=int, default=10, help='Maximum number of tasks to list')
        
        # Show task command
        show_task_parser = tasks_subparsers.add_parser('show', help='Show task details')
        show_task_parser.add_argument('task_id', help='ID of the task to show')
        
        # Cancel task command
        cancel_task_parser = tasks_subparsers.add_parser('cancel', help='Cancel a running task')
        cancel_task_parser.add_argument('task_id', help='ID of the task to cancel')
        
        # Visualization commands
        viz_parser = subparsers.add_parser('viz', help='Create visualizations')
        viz_subparsers = viz_parser.add_subparsers(dest='viz_command', help='Visualization command')
        
        # Site map visualization
        sitemap_viz_parser = viz_subparsers.add_parser('sitemap', help='Create site map visualization')
        sitemap_viz_parser.add_argument('input_file', help='Input JSON file with scrape results')
        sitemap_viz_parser.add_argument('--output', '-o', help='Output file path')
        sitemap_viz_parser.add_argument('--interactive', '-i', action='store_true', help='Create interactive visualization')
        
        # Word cloud visualization
        wordcloud_viz_parser = viz_subparsers.add_parser('wordcloud', help='Create word cloud visualization')
        wordcloud_viz_parser.add_argument('input_file', help='Input JSON file with scrape results')
        wordcloud_viz_parser.add_argument('--output', '-o', help='Output file path')
        wordcloud_viz_parser.add_argument('--field', default='text', help='Text field to use (default: text)')
        wordcloud_viz_parser.add_argument('--width', type=int, default=800, help='Width of word cloud')
        wordcloud_viz_parser.add_argument('--height', type=int, default=400, help='Height of word cloud')
        
        # Content analysis visualization
        content_viz_parser = viz_subparsers.add_parser('content', help='Create content analysis dashboard')
        content_viz_parser.add_argument('input_file', help='Input JSON file with scrape results')
        content_viz_parser.add_argument('--output', '-o', help='Output file path')
        content_viz_parser.add_argument('--interactive', '-i', action='store_true', help='Create interactive visualization')
        
        # System commands
        system_parser = subparsers.add_parser('system', help='System management commands')
        system_subparsers = system_parser.add_subparsers(dest='system_command', help='System command')
        
        # Status command
        status_parser = system_subparsers.add_parser('status', help='Show system status')
        
        # Config command
        config_parser = system_subparsers.add_parser('config', help='Configure settings')
        config_parser.add_argument('--output-dir', help='Set output directory for scrape results')
        config_parser.add_argument('--default-user-agent', help='Set default user agent')
        config_parser.add_argument('--max-workers', type=int, help='Set maximum worker processes')
        config_parser.add_argument('--show', action='store_true', help='Show current configuration')
        
        # Worker command
        worker_parser = system_subparsers.add_parser('worker', help='Worker management')
        worker_subparsers = worker_parser.add_subparsers(dest='worker_command', help='Worker command')
        
        # Start worker command
        start_worker_parser = worker_subparsers.add_parser('start', help='Start worker process')
        start_worker_parser.add_argument('--concurrency', type=int, default=4, help='Worker concurrency')
        
        # Stop worker command
        stop_worker_parser = worker_subparsers.add_parser('stop', help='Stop worker process')
        
        # Other optional global arguments
        parser.add_argument('--debug', action='store_true', help='Enable debug logging')
        parser.add_argument('--quiet', action='store_true', help='Suppress all output except errors')
        parser.add_argument('--config', help='Path to config file')
        parser.add_argument('--version', '-v', action='version', version='%(prog)s 1.0.0')
        
        return parser
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from config file.
        
        Returns:
            Dictionary of configuration values
        """
        config = {}
        
        # Default config file paths to check
        config_paths = [
            os.path.join(os.path.expanduser('~'), '.scrapy', 'config.ini'),
            os.path.join(root_dir, 'config.ini')
        ]
        
        # Look for config file
        config_file = None
        for path in config_paths:
            if os.path.exists(path):
                config_file = path
                break
        
        if config_file:
            try:
                parser = configparser.ConfigParser()
                parser.read(config_file)
                
                if 'DEFAULT' in parser:
                    for key, value in parser['DEFAULT'].items():
                        config[key] = value
                
                logger.debug(f"Loaded configuration from {config_file}")
            except Exception as e:
                logger.warning(f"Error reading config file: {e}")
        
        return config
    
    def _save_config(self, config: Dict[str, Any]) -> None:
        """
        Save configuration to config file.
        
        Args:
            config: Dictionary of configuration values to save
        """
        # Create config directory if it doesn't exist
        config_dir = os.path.join(os.path.expanduser('~'), '.scrapy')
        os.makedirs(config_dir, exist_ok=True)
        
        # Create or update config file
        config_file = os.path.join(config_dir, 'config.ini')
        
        try:
            parser = configparser.ConfigParser()
            
            # Load existing config if present
            if os.path.exists(config_file):
                parser.read(config_file)
            
            # Ensure DEFAULT section exists
            if 'DEFAULT' not in parser:
                parser['DEFAULT'] = {}
            
            # Update values
            for key, value in config.items():
                parser['DEFAULT'][key] = str(value)
            
            # Save file
            with open(config_file, 'w') as f:
                parser.write(f)
            
            logger.debug(f"Saved configuration to {config_file}")
        except Exception as e:
            logger.error(f"Error saving config file: {e}")
    
    def _set_log_level(self, args: argparse.Namespace) -> None:
        """
        Set the logging level based on command-line arguments.
        
        Args:
            args: Parsed command-line arguments
        """
        if args.debug:
            logging.getLogger().setLevel(logging.DEBUG)
            logger.debug("Debug logging enabled")
        elif args.quiet:
            logging.getLogger().setLevel(logging.ERROR)
    
    def _prepare_output_path(self, args: argparse.Namespace, default_name: str) -> str:
        """
        Prepare the output file path.
        
        Args:
            args: Parsed command-line arguments
            default_name: Default filename base
            
        Returns:
            Full path to save output
        """
        # If output is specified directly, use it
        if args.output:
            return args.output
        
        # Create timestamped filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{default_name}_{timestamp}.{args.format}"
        
        # Use output directory from config
        return os.path.join(self.output_dir, filename)
    
    def _save_output(self, data: Any, output_path: str, format_type: str) -> None:
        """
        Save data to the specified output format.
        
        Args:
            data: Data to save
            output_path: Path to save to
            format_type: Format type (json, csv, xlsx)
        """
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        
        if format_type == 'json':
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        elif format_type == 'csv':
            import pandas as pd
            
            # Convert to DataFrame
            df = self._convert_to_dataframe(data)
            df.to_csv(output_path, index=False, encoding='utf-8')
        elif format_type == 'xlsx':
            import pandas as pd
            
            # Convert to DataFrame
            df = self._convert_to_dataframe(data)
            df.to_excel(output_path, index=False)
        else:
            logger.error(f"Unsupported format: {format_type}")
            return
        
        logger.info(f"Output saved to {output_path}")
    
    def _convert_to_dataframe(self, data: Dict) -> 'pd.DataFrame':
        """
        Convert nested JSON data to a pandas DataFrame.
        
        Args:
            data: Data to convert
            
        Returns:
            pandas DataFrame
        """
        import pandas as pd
        
        # Extract pages data if available
        if isinstance(data, dict) and 'data' in data and 'pages' in data['data']:
            return pd.json_normalize(data['data']['pages'])
        elif isinstance(data, dict) and 'data' in data and isinstance(data['data'], list):
            return pd.json_normalize(data['data'])
        elif isinstance(data, list):
            return pd.json_normalize(data)
        else:
            # Fallback case
            return pd.json_normalize([data])
    
    def run(self, args: Optional[List[str]] = None) -> int:
        """
        Parse arguments and run the appropriate command.
        
        Args:
            args: Command line arguments (defaults to sys.argv)
            
        Returns:
            Exit code (0 for success, non-zero for errors)
        """
        # Parse arguments
        args = self.parser.parse_args(args)
        
        # Set logging level
        self._set_log_level(args)
        
        # Load custom config file if specified
        if hasattr(args, 'config') and args.config:
            try:
                parser = configparser.ConfigParser()
                parser.read(args.config)
                
                if 'DEFAULT' in parser:
                    for key, value in parser['DEFAULT'].items():
                        self.config[key] = value
                
                logger.debug(f"Loaded custom configuration from {args.config}")
            except Exception as e:
                logger.warning(f"Error reading custom config file: {e}")
        
        try:
            # Execute the specified command
            if args.command == 'scrape':
                return self._cmd_scrape(args)
            elif args.command == 'recursive':
                return self._cmd_recursive_scrape(args)
            elif args.command == 'adaptive':
                return self._cmd_adaptive_scrape(args)
            elif args.command == 'tasks':
                return self._cmd_tasks(args)
            elif args.command == 'viz':
                return self._cmd_visualization(args)
            elif args.command == 'system':
                return self._cmd_system(args)
            else:
                self.parser.print_help()
                return 0
                
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            if args.debug:
                import traceback
                logger.debug(traceback.format_exc())
            return 1
    
    def _cmd_scrape(self, args: argparse.Namespace) -> int:
        """
        Execute the scrape command.
        
        Args:
            args: Parsed command line arguments
            
        Returns:
            Exit code
        """
        logger.info(f"Scraping URL: {args.url}")
        
        # Set up the scraper
        scraper = WebpageScraper(output_dir=self.output_dir)
        
        # Set custom user agent if provided
        if args.user_agent:
            scraper.browser.set_user_agent(args.user_agent)
        
        # Set timeout if provided
        if args.timeout:
            scraper.browser.set_timeout(args.timeout)
        
        # Start timing
        start_time = time.time()
        
        # Perform the scrape
        result = scraper.save_webpage(
            url=args.url,
            follow_links=False,
            compile_text=not args.no_text,  # Skip text analysis if --no-text is specified
            save_screenshot=args.screenshot
        )
        
        # Calculate duration
        duration = time.time() - start_time
        result['duration'] = f"{duration:.2f} seconds"
        
        # Prepare output path
        output_path = self._prepare_output_path(
            args, 
            f"scrape_{self._get_domain(args.url)}"
        )
        
        # Save output
        self._save_output(result, output_path, args.format)
        
        # Show a summary
        self._print_scrape_summary(result)
        
        return 0
    
    def _cmd_recursive_scrape(self, args: argparse.Namespace) -> int:
        """
        Execute the recursive scrape command.
        
        Args:
            args: Parsed command line arguments
            
        Returns:
            Exit code
        """
        logger.info(f"Recursively scraping starting from URL: {args.url}")
        
        # Prepare configuration
        config = {
            'max_depth': args.depth,
            'max_pages': args.limit,
            'stay_on_domain': args.same_domain,
            'min_request_interval': args.delay
        }
        
        # Add URL patterns if provided
        if args.include:
            config['follow_url_patterns'] = args.include
            
        if args.exclude:
            config['exclude_url_patterns'] = args.exclude
            
        if args.respect_robots:
            config['respect_robots_txt'] = True
        
        # Set up the scraper
        scraper = RecursiveScraper(output_dir=self.output_dir, config=config)
        
        # Start timing
        start_time = time.time()
        
        # Perform the scrape
        result = scraper.start_crawl(args.url)
        
        # Calculate duration
        duration = time.time() - start_time
        result['duration'] = f"{duration:.2f} seconds"
        
        # Prepare output path
        output_path = self._prepare_output_path(
            args, 
            f"recursive_{self._get_domain(args.url)}"
        )
        
        # Save output
        self._save_output(result, output_path, args.format)
        
        # Show summary
        pages_count = len(result.get('data', {}).get('pages', []))
        logger.info(f"Recursive scrape complete. Scraped {pages_count} pages in {duration:.2f} seconds")
        
        return 0
    
    def _cmd_adaptive_scrape(self, args: argparse.Namespace) -> int:
        """
        Execute the adaptive scrape command.
        
        Args:
            args: Parsed command line arguments
            
        Returns:
            Exit code
        """
        logger.info(f"Adaptively scraping URL: {args.url}")
        
        # Set up the scraper
        scraper = AdaptiveScraper(output_dir=self.output_dir, use_ai=args.ai)
        
        # Start timing
        start_time = time.time()
        
        # Perform the scrape
        result = scraper.extract_data(
            url=args.url,
            data_type=args.type,
            save_screenshot=args.screenshot
        )
        
        # Calculate duration
        duration = time.time() - start_time
        result['duration'] = f"{duration:.2f} seconds"
        
        # Prepare output path
        output_path = self._prepare_output_path(
            args, 
            f"adaptive_{self._get_domain(args.url)}"
        )
        
        # Save output
        self._save_output(result, output_path, args.format)
        
        # Show summary
        if 'data' in result:
            if isinstance(result['data'], list):
                logger.info(f"Adaptive scrape complete. Extracted {len(result['data'])} items in {duration:.2f} seconds")
            else:
                logger.info(f"Adaptive scrape complete. Extracted data in {duration:.2f} seconds")
        
        return 0
    
    def _cmd_tasks(self, args: argparse.Namespace) -> int:
        """
        Execute tasks management commands.
        
        Args:
            args: Parsed command line arguments
            
        Returns:
            Exit code
        """
        if args.task_command == 'list':
            return self._cmd_list_tasks(args)
        elif args.task_command == 'show':
            return self._cmd_show_task(args)
        elif args.task_command == 'cancel':
            return self._cmd_cancel_task(args)
        else:
            logger.error("No task command specified. Use --help to see available commands.")
            return 1
    
    def _cmd_list_tasks(self, args: argparse.Namespace) -> int:
        """
        List tasks.
        
        Args:
            args: Parsed command line arguments
            
        Returns:
            Exit code
        """
        # Get filter status
        status_filter = None if args.status == 'all' else args.status
        
        # Get tasks
        tasks = db_manager.get_recent_tasks(limit=args.limit, status=status_filter)
        
        if not tasks:
            logger.info("No tasks found")
            return 0
        
        # Print tasks
        print("\nRecent Tasks:")
        print(f"{'ID':<10} {'Created':<20} {'Status':<12} {'Type':<15} {'URL':<50}")
        print("-" * 100)
        
        for task in tasks:
            created = task.get('created_at', 'N/A')
            if isinstance(created, str):
                # Try to parse and format the timestamp
                try:
                    dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                    created = dt.strftime('%Y-%m-%d %H:%M:%S')
                except ValueError:
                    pass
                    
            print(f"{task.get('id', 'N/A'):<10} "
                  f"{created:<20} "
                  f"{task.get('status', 'N/A'):<12} "
                  f"{task.get('job_type', 'N/A'):<15} "
                  f"{task.get('url', 'N/A')[:50]:<50}")
        
        print("")
        return 0
    
    def _cmd_show_task(self, args: argparse.Namespace) -> int:
        """
        Show task details.
        
        Args:
            args: Parsed command line arguments
            
        Returns:
            Exit code
        """
        # Get the task
        task = db_manager.get_task_details(args.task_id)
        
        if not task:
            logger.error(f"Task {args.task_id} not found")
            return 1
        
        # Print task details
        print(f"\nTask {args.task_id} Details")
        print("=" * 50)
        print(f"URL: {task.get('url', 'N/A')}")
        print(f"Type: {task.get('job_type', 'N/A')}")
        print(f"Status: {task.get('status', 'N/A')}")
        print(f"Created: {task.get('created_at', 'N/A')}")
        
        if task.get('started_at'):
            print(f"Started: {task.get('started_at')}")
            
        if task.get('completed_at'):
            print(f"Completed: {task.get('completed_at')}")
        
        if task.get('duration'):
            print(f"Duration: {task.get('duration')} seconds")
        
        # Show metadata if available
        if 'metadata' in task and task['metadata']:
            print("\nMetadata:")
            for key, value in task['metadata'].items():
                print(f"- {key}: {value}")
        
        # Show results path if available
        if 'result_path' in task and task['result_path']:
            print(f"\nResults saved to: {task['result_path']}")
        
        print("")
        return 0
    
    def _cmd_cancel_task(self, args: argparse.Namespace) -> int:
        """
        Cancel a running task.
        
        Args:
            args: Parsed command line arguments
            
        Returns:
            Exit code
        """
        # Try to cancel the task
        result = task_manager.cancel_task(args.task_id)
        
        if result:
            logger.info(f"Task {args.task_id} cancelled successfully")
            return 0
        else:
            logger.error(f"Failed to cancel task {args.task_id}")
            return 1
    
    def _cmd_visualization(self, args: argparse.Namespace) -> int:
        """
        Execute visualization commands.
        
        Args:
            args: Parsed command line arguments
            
        Returns:
            Exit code
        """
        if args.viz_command == 'sitemap':
            return self._cmd_viz_sitemap(args)
        elif args.viz_command == 'wordcloud':
            return self._cmd_viz_wordcloud(args)
        elif args.viz_command == 'content':
            return self._cmd_viz_content(args)
        else:
            logger.error("No visualization command specified. Use --help to see available commands.")
            return 1
    
    def _cmd_viz_sitemap(self, args: argparse.Namespace) -> int:
        """
        Create site map visualization.
        
        Args:
            args: Parsed command line arguments
            
        Returns:
            Exit code
        """
        logger.info(f"Creating site map visualization from {args.input_file}")
        
        # Initialize visualizer
        visualizer = ScrapyVisualizer(output_dir=self.output_dir)
        
        # Load data
        data = visualizer.load_data(args.input_file)
        
        # Prepare output path
        if args.output:
            output_path = args.output
        else:
            extension = 'html' if args.interactive else 'png'
            output_path = os.path.join(self.output_dir, f"sitemap_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{extension}")
        
        # Create visualization
        if args.interactive:
            fig = visualizer.create_interactive_site_map(data, save_path=output_path)
        else:
            fig = visualizer.create_site_map(data, save_path=output_path)
        
        if fig:
            logger.info(f"Site map visualization saved to {output_path}")
            return 0
        else:
            logger.error("Failed to create site map visualization")
            return 1
    
    def _cmd_viz_wordcloud(self, args: argparse.Namespace) -> int:
        """
        Create word cloud visualization.
        
        Args:
            args: Parsed command line arguments
            
        Returns:
            Exit code
        """
        logger.info(f"Creating word cloud visualization from {args.input_file}")
        
        # Initialize visualizer
        visualizer = ScrapyVisualizer(output_dir=self.output_dir)
        
        # Load data
        data = visualizer.load_data(args.input_file)
        
        # Prepare output path
        if args.output:
            output_path = args.output
        else:
            output_path = os.path.join(self.output_dir, f"wordcloud_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        
        # Create visualization
        fig = visualizer.create_word_cloud(
            data, 
            text_field=args.field,
            width=args.width,
            height=args.height,
            save_path=output_path
        )
        
        if fig:
            logger.info(f"Word cloud visualization saved to {output_path}")
            return 0
        else:
            logger.error("Failed to create word cloud visualization")
            return 1
    
    def _cmd_viz_content(self, args: argparse.Namespace) -> int:
        """
        Create content analysis visualization.
        
        Args:
            args: Parsed command line arguments
            
        Returns:
            Exit code
        """
        logger.info(f"Creating content analysis visualization from {args.input_file}")
        
        # Initialize visualizer
        visualizer = ScrapyVisualizer(output_dir=self.output_dir)
        
        # Load data
        data = visual