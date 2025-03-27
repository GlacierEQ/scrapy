# Scrapy: Advanced Web Scraping Toolkit

![Scrapy Logo](docs/assets/scrapy_logo.png)

A comprehensive toolkit for web scraping, data extraction, and analysis with advanced features for memory optimization, distributed processing, and data visualization.

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Documentation](https://img.shields.io/badge/docs-latest-brightgreen)](docs/index.md)

## 🌟 Features

- **Multiple Scraping Approaches**: From simple page scraping to adaptive content extraction
- **Browser Automation**: Headless browser support with stealth mode
- **Memory Optimization**: Handle large datasets efficiently with streaming and memory mapping
- **Distributed Scraping**: Scale your scraping with worker processes across multiple machines
- **Data Visualization**: Generate insights from scraped data with built-in visualization tools
- **Error Handling & Resilience**: Robust recovery mechanisms and proxy rotation
- **API & Command Line Interface**: Programmatic and CLI access to all features
- **Visual Scraper Builder**: Create scrapers without coding through a visual interface

## 🚀 Quick Start

### Installation

```bash
# Install required packages
pip install -r requirements.txt
```

### Simple Usage

```python
from scraping_project.general_webscraper import WebpageScraper

# Initialize a scraper
scraper = WebpageScraper()

# Scrape a webpage
result = scraper.save_webpage(
    url="https://example.com",
    follow_links=False,
    compile_text=True,
    save_screenshot=True
)

# Print the result
print(f"Title: {result['data']['pages'][0]['title']}")
print(f"Word count: {result['data']['pages'][0]['analysis']['content_analysis']['word_count']}")
```

### Command Line

```bash
# Simple scrape
python -m cli.scrapy_cli scrape https://example.com --screenshot

# Recursive scrape
python -m cli.scrapy_cli recursive https://example.com --depth 2 --limit 50

# Adaptive content extraction
python -m cli.scrapy_cli adaptive https://news.ycombinator.com --type list
```

## 📊 Visualization

Scrapy can generate visualizations from the scraped data:

```bash
# Generate a site map from scrape results
python -m cli.scrapy_cli viz sitemap results.json --interactive

# Create a word cloud from text content
python -m cli.scrapy_cli viz wordcloud results.json
```

## 🔧 Key Components

- **WebpageScraper**: Basic webpage scraping functionality
- **RecursiveScraper**: Follow links and scrape multiple pages
- **AdaptiveScraper**: Automatically detect and extract structured content
- **ResilientBrowser**: Browser automation with error recovery
- **MemoryManager**: Optimize memory usage for large datasets
- **ErrorHandler**: Handle and recover from errors
- **DataVisualizer**: Visualize scraped data
- **ScrapyAPI**: REST API for remote access to scraping functionality
- **VisualBuilder**: Create scrapers through a visual interface

## 💾 Memory Optimization

For handling large datasets, Scrapy provides advanced memory optimization:

```python
from scraping_project.memory_expansion import MemoryMappedFile, StreamingProcessor

# Process a large file without loading it fully into memory
with MemoryMappedFile('large_dataset.json') as mmfile:
    data = mmfile.read()
    
# Process large JSON files in chunks
processor = StreamingProcessor()
results = processor.process_large_json(
    filepath='large_data.json',
    processor_func=lambda item: transform_data(item),
    array_path='results.items'
)
```

## 🌐 API Usage

The Scrapy API allows you to use all functionality remotely:

```python
from clients.python.scrapy_client import ScrapyClient

# Initialize client
client = ScrapyClient(api_key="your_api_key")

# Perform an adaptive scrape
result = client.adaptive_scrape(
    url="https://example.com/products",
    data_type="product",
    use_ai=True
)
```

## 📦 Example Projects

Check out complete working examples in the `examples` directory:

- **[E-commerce Scraper](examples/complete/ecommerce_scraper.py)**: Complete e-commerce product scraper
- **[News Aggregator](examples/news_aggregator.py)**: Collect and analyze news articles
- **[Content Analyzer](examples/content_analyzer.py)**: Extract and analyze content from multiple sources

## 📚 Documentation

Comprehensive documentation is available in the [docs](docs/index.md) directory:

- [Installation Guide](docs/installation.md)
- [Quick Start Guide](docs/quickstart.md)
- [API Reference](docs/reference/api.md)
- [Advanced Features Guide](docs/advanced/README.md)
- [Best Practices](docs/best_practices/README.md)

## 🤝 Contributing

Contributions are welcome! Please check out our [contributing guidelines](CONTRIBUTING.md).

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📞 Contact

For questions and support, please [open an issue](https://github.com/yourusername/scrapy/issues).
