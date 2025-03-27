"""
Advanced memory management for handling large datasets.

This module provides enhanced memory management capabilities including:
- Memory-mapped files for processing large datasets
- Streaming processors for memory-efficient operations
- Automatic memory monitoring and optimization
- Chunking functions for big data workloads
"""

import os
import sys
import mmap
import json
import pickle
import logging
import tempfile
import gc
import threading
import time
import warnings
import io
import csv
import gzip
import bz2
import lzma
from typing import Dict, List, Any, Optional, Union, Iterator, Callable, Generator, BinaryIO, TextIO
from contextlib import contextmanager
import numpy as np
from pathlib import Path
from datetime import datetime

from .memory_manager import get_memory_manager, MemoryManager

# Configure logging
logger = logging.getLogger(__name__)

class MemoryMappedFile:
    """
    Memory-mapped file handler for efficient processing of large files.
    
    This class provides a memory-efficient way to work with large files
    by using memory mapping instead of loading the entire file into RAM.
    """
    
    def __init__(self, 
                 filepath: str, 
                 mode: str = 'r', 
                 access: int = mmap.ACCESS_READ):
        """
        Initialize a memory-mapped file.
        
        Args:
            filepath: Path to the file to memory-map
            mode: File open mode ('r' for read, 'w+' for read/write)
            access: Memory access mode (ACCESS_READ, ACCESS_WRITE, ACCESS_COPY)
        """
        self.filepath = filepath
        self.mode = mode
        self.access = access
        self.file = None
        self.mmapped_file = None
        self.size = 0
        
        if mode == 'r':
            file_mode = 'rb'
        else:
            file_mode = 'r+b'  # Read and write binary
        
        try:
            self.file = open(filepath, file_mode)
            self.size = os.path.getsize(filepath)
            
            # Only create memory mapping if the file has content
            if self.size > 0:
                self.mmapped_file = mmap.mmap(
                    self.file.fileno(),
                    0,  # 0 = map the entire file
                    access=access
                )
        except Exception as e:
            logger.error(f"Error memory-mapping file {filepath}: {e}")
            if self.file:
                self.file.close()
            raise
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.close()
    
    def close(self):
        """Close the memory-mapped file and underlying file object."""
        if self.mmapped_file:
            self.mmapped_file.close()
            self.mmapped_file = None
        
        if self.file:
            self.file.close()
            self.file = None
    
    def read(self, size: int = -1, offset: int = 0) -> bytes:
        """
        Read from the memory-mapped file.
        
        Args:
            size: Number of bytes to read, -1 for entire file
            offset: Byte offset to start reading from
            
        Returns:
            Bytes read from the file
        """
        if not self.mmapped_file:
            raise ValueError("Memory-mapped file is not open or empty")
        
        if offset > 0:
            self.mmapped_file.seek(offset)
        
        if size < 0:
            return self.mmapped_file[offset:]
        else:
            return self.mmapped_file[offset:offset+size]
    
    def readline(self, offset: int = None) -> bytes:
        """
        Read a line from the memory-mapped file.
        
        Args:
            offset: Optional byte offset to start reading from
            
        Returns:
            Line read from the file as bytes
        """
        if not self.mmapped_file:
            raise ValueError("Memory-mapped file is not open or empty")
        
        if offset is not None:
            self.mmapped_file.seek(offset)
        
        return self.mmapped_file.readline()
    
    def search(self, pattern: bytes, start: int = 0) -> int:
        """
        Search for a byte pattern in the memory-mapped file.
        
        Args:
            pattern: Byte pattern to search for
            start: Start position for the search
            
        Returns:
            Position where pattern was found, or -1 if not found
        """
        if not self.mmapped_file:
            raise ValueError("Memory-mapped file is not open or empty")
        
        self.mmapped_file.seek(start)
        result = self.mmapped_file.find(pattern)
        return result
    
    def write(self, data: bytes, offset: int = None) -> int:
        """
        Write to the memory-mapped file.
        
        Args:
            data: Byte data to write
            offset: Optional byte offset to write at
            
        Returns:
            Number of bytes written
        """
        if not self.mmapped_file or self.access == mmap.ACCESS_READ:
            raise ValueError("File not open for writing")
        
        if offset is not None:
            self.mmapped_file.seek(offset)
        
        return self.mmapped_file.write(data)
    
    def flush(self):
        """Flush changes to disk."""
        if self.mmapped_file:
            self.mmapped_file.flush()
    
    def __len__(self):
        """Return the file size."""
        return self.size
    
    def __getitem__(self, index):
        """Support slicing operations on the memory-mapped file."""
        if not self.mmapped_file:
            raise ValueError("Memory-mapped file is not open or empty")
        
        return self.mmapped_file[index]


class StreamingProcessor:
    """
    Process large datasets in a memory-efficient streaming manner.
    
    This class provides utilities for processing large datasets without
    loading all data into memory at once.
    """
    
    def __init__(self, chunk_size: int = 10000):
        """
        Initialize a streaming processor.
        
        Args:
            chunk_size: Number of items to process in each chunk
        """
        self.chunk_size = chunk_size
        self.memory_manager = get_memory_manager()
    
    def process_large_json(self, 
                           filepath: str, 
                           processor_func: Callable[[Dict], Any],
                           array_path: Optional[str] = None) -> List[Any]:
        """
        Process a large JSON file without loading it entirely into memory.
        
        Args:
            filepath: Path to the JSON file
            processor_func: Function to process each item
            array_path: Optional JSON path to an array within the JSON document
            
        Returns:
            List of processed results
        """
        import json
        from ijson import parse
        
        results = []
        
        # For handling array_path like "results.items"
        path_parts = array_path.split('.') if array_path else []
        current_path = []
        in_target_array = False
        current_item = None
        
        with open(filepath, 'rb') as f:
            for prefix, event, value in parse(f):
                # Track path to determine if we're in the target array
                if event == 'start_map':
                    if not array_path:
                        # Process the entire JSON as one item
                        current_item = json.loads(f.read().decode('utf-8'))
                        results.append(processor_func(current_item))
                        break
                elif event == 'start_array':
                    current_path.append(prefix)
                    current_path_str = '.'.join(current_path)
                    if current_path_str == array_path:
                        in_target_array = True
                elif event == 'end_array':
                    if in_target_array and '.'.join(current_path) == array_path:
                        in_target_array = False
                    if current_path:
                        current_path.pop()
                elif event == 'end_map':
                    if in_target_array and current_item:
                        results.append(processor_func(current_item))
                        current_item = None
                        
                        # Check memory and potentially free up resources
                        if len(results) % self.chunk_size == 0:
                            self.memory_manager._check_memory()
                elif in_target_array:
                    if event == 'start_map':
                        current_item = {}
                    elif current_item is not None:
                        if '.' in prefix:
                            # Handle nested fields
                            parts = prefix.split('.')
                            obj = current_item
                            for part in parts[:-1]:
                                if part not in obj:
                                    obj[part] = {}
                                obj = obj[part]
                            obj[parts[-1]] = value
                        else:
                            current_item[prefix] = value
        
        return results
    
    def stream_large_csv(self, 
                         filepath: str, 
                         processor_func: Callable[[Dict], Any],
                         delimiter: str = ',',
                         quotechar: str = '"') -> Generator[Any, None, None]:
        """
        Stream process a large CSV file row by row.
        
        Args:
            filepath: Path to the CSV file
            processor_func: Function to process each row
            delimiter: CSV delimiter character
            quotechar: CSV quote character
            
        Returns:
            Generator yielding processed results
        """
        processed_count = 0
        
        # Detect if the file is compressed based on extension
        open_func = open
        if filepath.endswith('.gz'):
            open_func = gzip.open
        elif filepath.endswith('.bz2'):
            open_func = bz2.open
        elif filepath.endswith('.xz'):
            open_func = lzma.open
        
        with open_func(filepath, 'rt', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=delimiter, quotechar=quotechar)
            
            for row in reader:
                # Process the row
                result = processor_func(row)
                yield result
                
                processed_count += 1
                
                # Check memory and potentially free up resources
                if processed_count % self.chunk_size == 0:
                    self.memory_manager._check_memory()
    
    def process_large_file(self, 
                           filepath: str, 
                           line_processor: Callable[[str], Any],
                           skip_lines: int = 0) -> Generator[Any, None, None]:
        """
        Process a large text file line by line.
        
        Args:
            filepath: Path to the text file
            line_processor: Function to process each line
            skip_lines: Number of lines to skip at the beginning
            
        Returns:
            Generator yielding processed results
        """
        processed_count = 0
        
        # Detect if the file is compressed based on extension
        open_func = open
        if filepath.endswith('.gz'):
            open_func = gzip.open
        elif filepath.endswith('.bz2'):
            open_func = bz2.open
        elif filepath.endswith('.xz'):
            open_func = lzma.open
        
        with open_func(filepath, 'rt', encoding='utf-8') as f:
            # Skip the specified number of lines
            for _ in range(skip_lines):
                next(f, None)
            
            # Process the remaining lines
            for line in f:
                # Process the line
                result = line_processor(line.rstrip('\r\n'))
                yield result
                
                processed_count += 1
                
                # Check memory and potentially free up resources
                if processed_count % self.chunk_size == 0:
                    self.memory_manager._check_memory()
    
    def batch_process(self, 
                      items: List[Any], 
                      processor_func: Callable[[List[Any]], List[Any]],
                      batch_size: int = None) -> List[Any]:
        """
        Process a large list in batches to control memory usage.
        
        Args:
            items: List of items to process
            processor_func: Function to process each batch of items
            batch_size: Size of each batch (defaults to chunk_size)
            
        Returns:
            List of processed results
        """
        if batch_size is None:
            batch_size = self.chunk_size
        
        results = []
        total_items = len(items)
        
        for i in range(0, total_items, batch_size):
            # Get the current batch
            batch = items[i:i + batch_size]
            
            # Process the batch
            batch_results = processor_func(batch)
            results.extend(batch_results)
            
            # Free memory and run garbage collection if needed
            self.memory_manager._check_memory()
            
            # Log progress
            logger.debug(f"Processed {min(i + batch_size, total_items)}/{total_items} items")
        
        return results


class MemoryOptimizedDataHandler:
    """
    Handler for memory-efficient data operations on large datasets.
    
    This class provides utilities for working with large datasets using
    memory mapping, chunking, and streaming techniques.
    """
    
    def __init__(self, temp_dir: Optional[str] = None):
        """
        Initialize a memory-optimized data handler.
        
        Args:
            temp_dir: Directory for temporary files
        """
        self.memory_manager = get_memory_manager()
        self.temp_dir = temp_dir or tempfile.gettempdir()
        self.temp_files = []
        
        # Create the temp directory if it doesn't exist
        os.makedirs(self.temp_dir, exist_ok=True)
    
    def __del__(self):
        """Clean up temporary files on deletion."""
        self.cleanup()
    
    def cleanup(self):
        """Remove all temporary files created by this handler."""
        for filepath in self.temp_files:
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception as e:
                logger.warning(f"Error removing temporary file {filepath}: {e}")
        self.temp_files = []
    
    @contextmanager
    def create_temp_file(self, suffix: str = ".tmp") -> str:
        """
        Create a temporary file and clean it up when done.
        
        Args:
            suffix: File extension for the temporary file
            
        Returns:
            Path to the temporary file
        """
        fd, filepath = tempfile.mkstemp(suffix=suffix, dir=self.temp_dir)
        os.close(fd)  # Close the file descriptor
        self.temp_files.append(filepath)
        
        try:
            yield filepath
        finally:
            # File will be cleaned up in cleanup() method
            pass
    
    def load_json_in_chunks(self, 
                            filepath: str, 
                            chunk_size: int = 1000) -> Generator[List[Dict], None, None]:
        """
        Load a JSON array in chunks to minimize memory usage.
        
        Args:
            filepath: Path to the JSON file containing an array
            chunk_size: Number of items to load in each chunk
            
        Returns:
            Generator yielding chunks of the JSON array
        """
        import json
        from ijson import items
        
        chunk = []
        
        with open(filepath, 'rb') as f:
            # Parse the outer array items one at a time
            for item in items(f, 'item'):
                chunk.append(item)
                
                if len(chunk) >= chunk_size:
                    yield chunk
                    chunk = []
                    self.memory_manager._check_memory()
        
        # Yield any remaining items
        if chunk:
            yield chunk
    
    def load_large_csv_as_chunks(self, 
                                filepath: str, 
                                chunk_size: int = 1000, 
                                delimiter: str = ',',
                                quotechar: str = '"') -> Generator[List[Dict], None, None]:
        """
        Load a large CSV file in chunks.
        
        Args:
            filepath: Path to the CSV file
            chunk_size: Number of rows to load in each chunk
            delimiter: CSV delimiter character
            quotechar: CSV quote character
            
        Returns:
            Generator yielding chunks of CSV rows
        """
        # Detect if the file is compressed based on extension
        open_func = open
        if filepath.endswith('.gz'):
            open_func = gzip.open
        elif filepath.endswith('.bz2'):
            open_func = bz2.open
        elif filepath.endswith('.xz'):
            open_func = lzma.open
        
        with open_func(filepath, 'rt', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=delimiter, quotechar=quotechar)
            
            chunk = []
            for row in reader:
                chunk.append(row)
                
                if len(chunk) >= chunk_size:
                    yield chunk
                    chunk = []
                    self.memory_manager._check_memory()
            
            # Yield any remaining rows
            if chunk:
                yield chunk
    
    def save_as_memory_mapped_array(self, 
                                   data: Union[List, np.ndarray], 
                                   filepath: Optional[str] = None,
                                   dtype=None) -> Tuple[str, np.ndarray]:
        """
        Save data as a memory-mapped numpy array for efficient access.
        
        Args:
            data: List or numpy array to save
            filepath: Optional path to save the array (creates temp file if None)
            dtype: Data type for the numpy array
            
        Returns:
            Tuple of (filepath, memory-mapped array)
        """
        # Convert to numpy array if necessary
        if not isinstance(data, np.ndarray):
            array = np.array(data, dtype=dtype)
        else:
            array = data
        
        # Create a temporary file if filepath not provided
        if filepath is None:
            with self.create_temp_file(suffix=".npy") as temp_filepath:
                filepath = temp_filepath
        
        # Save as memory-mapped array
        mmap_array = np.memmap(filepath, dtype=array.dtype, mode='w+', shape=array.shape)
        mmap_array[:] = array[:]
        mmap_array.flush()
        
        return filepath, mmap_array
    
    def open_memory_mapped_array(self, 
                               filepath: str, 
                               mode: str = 'r',
                               dtype=None,
                               shape=None) -> np.ndarray:
        """
        Open a memory-mapped numpy array from a file.
        
        Args:
            filepath: Path to the numpy array file
            mode: Access mode ('r' for read-only, 'r+' for read-write)
            dtype: Data type of the array
            shape: Shape of the array (required if not a .npy file)
            
        Returns:
            Memory-mapped numpy array
        """
        if filepath.endswith('.npy'):
            # For .npy files, we can just use memmap directly
            return np.load(filepath, mmap_mode=mode)
        else:
            # For raw binary data, we need dtype and shape
            if dtype is None or shape is None:
                raise ValueError("dtype and shape must be provided for non-.npy files")
            
            return np.memmap(filepath, dtype=dtype, mode=mode, shape=shape)
    
    def create_memory_efficient_dataset(self, 
                                       data: List[Dict], 
                                       filepath: Optional[str] = None) -> str:
        """
        Create a memory-efficient dataset from a list of dictionaries.
        
        Args:
            data: List of dictionaries to save
            filepath: Optional path to save the dataset
            
        Returns:
            Path to the created dataset file
        """
        # Create a temporary file if filepath not provided
        if filepath is None:
            with self.create_temp_file(suffix=".npz") as temp_filepath:
                filepath = temp_filepath
        
        # Extract column names and data
        if not data:
            raise ValueError("Data list is empty")
        
        # Get all unique keys from all dictionaries
        all_keys = set()
        for item in data:
            all_keys.update(item.keys())
        
        # Create a dictionary of arrays for each key
        arrays = {}
        for key in all_keys:
            # Extract the values, using None for missing values
            values = [item.get(key) for item in data]
            arrays[key] = np.array(values, dtype=object)
        
        # Save as compressed numpy zip file
        np.savez_compressed(filepath, **arrays)
        
        return filepath
    
    def load_memory_efficient_dataset(self, 
                                     filepath: str) -> Dict[str, np.ndarray]:
        """
        Load a memory-efficient dataset.
        
        Args:
            filepath: Path to the dataset file
            
        Returns:
            Dictionary of arrays
        """
        # Load the numpy zip file
        npz_file = np.load(filepath, allow_pickle=True)
        
        # Convert to dictionary
        return {key: npz_file[key] for key in npz_file.files}
    
    def convert_to_memory_efficient_format(self,
                                         input_filepath: str,
                                         output_filepath: Optional[str] = None,
                                         format_type: str = 'auto') -> str:
        """
        Convert a file to a memory-efficient format.
        
        Args:
            input_filepath: Path to the input file
            output_filepath: Path for the output file
            format_type: Target format ('npz', 'hdf5', 'parquet', 'auto')
            
        Returns:
            Path to the converted file
        """
        # Determine format type if auto
        if format_type == 'auto':
            # Choose based on file size and available libraries
            if os.path.getsize(input_filepath) > 1e9:  # > 1GB
                try:
                    import h5py
                    format_type = 'hdf5'
                except ImportError:
                    try:
                        import pyarrow
                        format_type = 'parquet'
                    except ImportError:
                        format_type = 'npz'
            else:
                format_type = 'npz'
        
        # Create a temporary file if output_filepath not provided
        if output_filepath is None:
            suffix = f".{format_type}" if format_type != 'hdf5' else '.h5'
            with self.create_temp_file(suffix=suffix) as temp_filepath:
                output_filepath = temp_filepath
        
        # Detect input file type and convert
        input_ext = os.path.splitext(input_filepath)[1].lower()
        
        if input_ext == '.json':
            # Convert JSON to the target format
            if format_type == 'npz':
                with open(input_filepath, 'r') as f:
                    data = json.load(f)
                
                # Handle different JSON structures
                if isinstance(data, list) and all(isinstance(item, dict) for item in data):
                    self.create_memory_efficient_dataset(data, output_filepath)
                else:
                    # For non-uniform structures, use object arrays
                    np.savez_compressed(output_filepath, data=np.array([data], dtype=object))
                    
            elif format_type == 'hdf5':
                import h5py
                streaming_processor = StreamingProcessor()
                
                with h5py.File(output_filepath, 'w') as h5f:
                    for chunk in streaming_processor.process_large_json(input_filepath, lambda x: x, array_path=''):
                        # Convert chunk to a format that can be stored in HDF5
                        pass
                        
            elif format_type == 'parquet':
                import pyarrow as pa
                import pyarrow.parquet as pq
                
                with open(input_filepath, 'r') as f:
                    data = json.load(f)
                
                # Convert to arrow table and write to parquet
                if isinstance(data, list) and all(isinstance(item, dict) for item in data):
                    table = pa.Table.from_pylist(data)
                    pq.write_table(table, output_filepath)
        
        elif input_ext == '.csv':
            # Convert CSV to the target format
            if format_type == 'npz':
                chunks = []
                for chunk in self.load_large_csv_as_chunks(input_filepath):
                    chunks.extend(chunk)
                    
                self.create_memory_efficient_dataset(chunks, output_filepath)
                
            elif format_type == 'hdf5':
                import h5py
                import pandas as pd
                
                # Use pandas to read CSV in chunks
                chunk_size = 10000
                with h5py.File(output_filepath, 'w') as h5f:
                    for i, chunk in enumerate(pd.read_csv(input_filepath, chunksize=chunk_size)):
                        # Store each chunk as a dataset
                        h5f.create_dataset(f'chunk_{i}', data=chunk.to_numpy())
                        # Also store column names
                        if i == 0:
                            h5f.attrs['columns'] = chunk.columns.tolist()
                            
            elif format_type == 'parquet':
                import pandas as pd
                
                # Read CSV and convert to parquet
                df = pd.read_csv(input_filepath)
                df.to_parquet(output_filepath)
        
        return output_filepath
    
    def memory_efficient_record_iterator(self, 
                                        filepath: str) -> Generator[Dict[str, Any], None, None]:
        """
        Create a memory-efficient iterator for records in a file.
        
        Args:
            filepath: Path to the file
            
        Returns:
            Generator yielding records
        """
        # Determine file type based on extension
        ext = os.path.splitext(filepath)[1].lower()
        
        if ext == '.json':
            # Use ijson to stream JSON parsing
            from ijson import items
            
            with open(filepath, 'rb') as f:
                for item in items(f, 'item'):
                    yield item
                    
        elif ext == '.csv':
            # Stream CSV parsing
            with open(filepath, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    yield row
                    
        elif ext in ('.npz', '.npy'):
            # Handle numpy data
            data = np.load(filepath, allow_pickle=True)
            
            if ext == '.npz':
                # For npz, we need to reconstruct records from arrays
                keys = data.files
                length = len(data[keys[0]])
                
                for i in range(length):
                    record = {key: data[key][i] for key in keys}
                    yield record
            else:
                # For npy, just yield each item
                for item in data:
                    yield item
                    
        elif ext in ('.h5', '.hdf5'):
            # Handle HDF5 files
            import h5py
            
            with h5py.File(filepath, 'r') as f:
                # Get column names from attributes
                columns = f.attrs.get('columns', [])
                
                # Iterate through all datasets
                for key in f.keys():
                    dataset = f[key]
                    
                    if isinstance(dataset, h5py.Dataset):
                        # For each row in the dataset
                        for i in range(dataset.shape[0]):
                            row = dataset[i]
                            
                            if columns:
                                # If we have column names, create a dictionary
                                yield {columns[j]: row[j] for j in range(len(columns))}
                            else:
                                # Otherwise just yield the raw row
                                yield row
                                
        elif ext == '.parquet':
            # Handle parquet files
            import pyarrow.parquet as pq
            
            # Open the file
            table = pq.read_table(filepath)
            
            # Convert to pandas for easier iteration
            df = table.to_pandas()
            
            # Yield each row as a dictionary
            for _, row in df.iterrows():
                yield row.to_dict()
        else:
            raise ValueError(f"Unsupported file format: {ext}")


class BigDataProcessor:
    """
    Process big data that might not fit in memory all at once.
    
    This class provides utilities for working with very large datasets
    using chunking, parallel processing, and memory-mapped files.
    """
    
    def __init__(self, 
                 max_memory_percent: float = 80.0,
                 temp_dir: Optional[str] = None,
                 parallel: bool = True,
                 n_jobs: int = -1):
        """
        Initialize a big data processor.
        
        Args:
            max_memory_percent: Maximum memory usage percent
            temp_dir: Directory for temporary files
            parallel: Whether to use parallel processing
            n_jobs: Number of parallel jobs (-1 for all available cores)
        """
        self.memory_manager = get_memory_manager()
        self.memory_manager.set_warning_threshold(max_memory_percent - 10)
        self.memory_manager.set_critical_threshold(max_memory_percent)
        
        self.temp_dir = temp_dir or tempfile.gettempdir()
        self.parallel = parallel
        self.n_jobs = n_jobs
        self.data_handler = MemoryOptimizedDataHandler(self.temp_dir)
    
    def __del__(self):
        """Clean up temporary files on deletion."""
        self.cleanup()
    
    def cleanup(self):
        """Clean up resources."""
        self.data_handler.cleanup()
    
    def process_big_data(self, 
                        data_source: Union[str, List],
                        processor_func: Callable,
                        chunk_size: Optional[int] = None,
                        output_path: Optional[str] = None,
                        output_format: str = 'json',
                        batch_mode: bool = True) -> Union[str, List]:
        """
        Process big data in chunks, optimizing for memory usage.
        
        Args:
            data_source: File path or list of data
            processor_func: Function to process each chunk
            chunk_size: Size of processing chunks
            output_path: Path to save results
            output_format: Format to save results ('json', 'csv', 'npz')
            batch_mode: Whether processor_func processes batches
            
        Returns:
            Path to the results