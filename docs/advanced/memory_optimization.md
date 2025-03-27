# Memory Optimization

When working with large datasets or scraping many pages, memory management becomes crucial. Scrapy provides advanced memory optimization tools to handle large-scale scraping jobs efficiently.

## Understanding Memory Challenges

Web scraping can consume significant memory for several reasons:
- HTML content from many pages being stored in memory
- Images and other binary content
- Parsing overhead when processing HTML
- Result data structures growing as more pages are scraped

## Memory Manager

The `MemoryManager` class monitors and controls memory usage during scraping operations:

```python
from scraping_project.memory_manager import get_memory_manager

# Get the singleton memory manager instance
memory_manager = get_memory_manager()

# Set memory usage thresholds
memory_manager.set_warning_threshold(70)  # Warn at 70% usage
memory_manager.set_critical_threshold(85)  # Take action at 85% usage

# Check current memory usage
usage = memory_manager.get_memory_usage()
print(f"System memory: {usage['system_percent']}%")
print(f"Process memory: {usage['process_rss_mb']} MB")
```

## Memory-Mapped Files

For handling files that are too large to fit in memory, use memory-mapped files:

```python
from scraping_project.memory_expansion import MemoryMappedFile

# Open a large file without loading it entirely into memory
with MemoryMappedFile('very_large_file.html') as mmfile:
    # Read the first 1000 bytes
    header = mmfile.read(1000)
    
    # Search for a specific pattern
    position = mmfile.search(b'<div class="content">')
    
    if position >= 0:
        # Read 500 bytes starting from the found position
        content = mmfile.read(500, offset=position)
```

## Streaming Processing

Process large files or datasets without loading them entirely:

```python
from scraping_project.memory_expansion import StreamingProcessor

processor = StreamingProcessor(chunk_size=5000)

# Process a large JSON file
results = processor.process_large_json(
    filepath='large_dataset.json',
    processor_func=lambda item: item['name'].upper(),
    array_path='results.items'
)

# Stream process a large CSV file
for processed_row in processor.stream_large_csv(
    filepath='large_data.csv',
    processor_func=lambda row: {k: v.strip() for k, v in row.items()}
):
    print(processed_row)
```

## Optimized Data Handler

For complex operations on large datasets:

```python
from scraping_project.memory_expansion import MemoryOptimizedDataHandler

handler = MemoryOptimizedDataHandler()

# Load a large JSON file in manageable chunks
for chunk in handler.load_json_in_chunks('massive_array.json', chunk_size=1000):
    # Process each chunk
    processed_chunk = [process_item(item) for item in chunk]
    # Save or further process the results
    save_partial_results(processed_chunk)

# Convert files to memory-efficient formats
efficient_path = handler.convert_to_memory_efficient_format(
    input_filepath='large_results.json',
    format_type='npz'  # Compressed NumPy format
)

# Create memory-mapped arrays for efficient access
filepath, mmap_array = handler.save_as_memory_mapped_array(
    data=large_data_list,
    dtype=np.float32
)

# Access data without loading it all in memory
for record in handler.memory_efficient_record_iterator('huge_dataset.json'):
    process_single_record(record)
```

## BigDataProcessor

For the largest datasets that might not fit in memory:

```python
from scraping_project.memory_expansion import BigDataProcessor

processor = BigDataProcessor(
    max_memory_percent=80.0,
    parallel=True
)

result_path = processor.process_big_data(
    data_source='enormous_dataset.json',
    processor_func=transform_data,
    chunk_size=10000,
    output_path='processed_results.json',
    batch_mode=True
)
```

## Best Practices

1. **Monitor Memory Usage**: Regularly check memory consumption during large scraping jobs.

2. **Use Chunk Processing**: Process data in chunks rather than all at once:
   ```python
   # Instead of this:
   all_results = [process(item) for item in huge_list]
   
   # Do this:
   results = []
   for chunk in chunks(huge_list, 1000):
       results.extend([process(item) for item in chunk])
       gc.collect()  # Force garbage collection after each chunk
   ```

3. **Clean Temporary Data**: Remove temporary files and data structures when they're no longer needed.

4. **Use Generators**: Use generator expressions instead of lists when possible:
   ```python
   # Instead of:
   all_texts = [extract_text(page) for page in pages]
   
   # Use:
   for text in (extract_text(page) for page in pages):
       process_text(text)
   ```

5. **Set Memory Thresholds**: Configure memory thresholds appropriate for your system.

6. **Compress When Possible**: Use compressed formats for intermediate storage.

## Configuration Options

You can configure memory optimization through the config file:

```ini
[memory]
warning_threshold = 70
critical_threshold = 85
check_interval = 5
enable_auto_cleanup = true
temp_directory = /path/to/temp/dir
```

Or through environment variables:
```bash
export SCRAPY_MEMORY_WARNING_THRESHOLD=70
export SCRAPY_MEMORY_CRITICAL_THRESHOLD=85
```

## Real-world Examples

### Scraping Millions of Pages

```python
from scraping_project.recursive_scraper import RecursiveScraper
from scraping_project.memory_expansion import BigDataProcessor

# Configure scraper with memory optimizations
scraper = RecursiveScraper(
    config={
        'max_pages': 1000000,
        'optimize_memory': True,
        'use_disk_storage': True,
        'checkpoint_interval': 1000  # Save state every 1000 pages
    }
)

# Use big data processor to handle results
processor = BigDataProcessor()

# Start the crawl
result = scraper.start_crawl('https://example.com')

# Process the massive results efficiently
processed_data = processor.process_big_data(
    data_source=result['data_path'],
    processor_func=extract_key_information,
    output_path='final_results.json'
)
```

### Processing Large Export Files

```python
from scraping_project.memory_expansion import StreamingProcessor

processor = StreamingProcessor()

# Process a 50GB export file without memory issues
for item in processor.process_large_file(
    filepath='massive_export.json.gz',
    line_processor=json.loads,
    skip_lines=1  # Skip header
):
    # Process each item individually
    if matches_criteria(item):
        save_to_database(item)
```

## Troubleshooting

If you encounter memory issues:

1. **Check Memory Usage**: Use the memory manager to monitor usage patterns.
2. **Increase Chunk Size**: Adjust chunk sizes based on your system capabilities.
3. **Use Disk Storage**: Enable disk-based storage for intermediate results.
4. **Reduce Concurrency**: Lower the number of concurrent scraping tasks.
5. **Memory Profiling**: Use tools like `memory_profiler` to identify memory bottlenecks.

```python
@memory_profiler.profile
def my_scraping_function(url):
    # Your code here
    pass
```

## Next Steps

- Learn about [Distributed Scraping](distributed_scraping.md) to spread the load across multiple machines
- Explore [Browser Management](../tools/browser_management.md) to optimize browser memory usage
- Check out [Performance Optimization](../best_practices/performance.md) for overall efficiency tips
