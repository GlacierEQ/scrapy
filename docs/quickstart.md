# Quick Start Guide

This guide will help you get started with Scrapy quickly. You'll learn how to install the toolkit, create your first scraper, and extract data from websites.

## Installation

### Prerequisites

* Python 3.8 or higher
* pip (Python package installer)
* Chrome or Chromium browser (for browser-based scraping)

### Installing Scrapy

```bash
pip install scrapy-toolkit
```

This command installs the core Scrapy toolkit and its required dependencies.

For visualization support, install additional dependencies:

```bash
pip install scrapy-toolkit[viz]
```

For the full feature set including AI-powered extraction:

```bash
pip install scrapy-toolkit[all]
```

## Your First Scrape

Let's start with a simple scrape of a webpage:

```bash
scrapy scrape https://quotes.toscrape.com
```

This command will:
1. Launch a browser
2. Visit the specified URL
3. Extract the content
4. Save the results to the default output directory

The output will include:
- A JSON file with the extracted data
- A screenshot of the page (if requested)
- A copy of the HTML content
- Text analysis of the content

## Viewing the Results

By default, results are saved to the `~/scrapy_output` directory. You can check the results with:

```bash
ls ~/scrapy_output
```

To view the JSON data, you can use a tool like `jq`:

```bash
cat ~/scrapy_output/scrape_quotes.toscrape.com_20230801_120000.json | jq
```

## Basic Scraping with Python

You can also use Scrapy programmatically in Python:

```python
from scraping_project.general_webscraper import WebpageScraper

# Initialize a scraper
scraper = WebpageScraper()

# Scrape a webpage
result = scraper.save_webpage(
    url="https://quotes.toscrape.com",
    follow_links=False,
    compile_text=True,
    save_screenshot=True
)

# Print the result
print(f"Title: {result['data']['pages'][0]['title']}")
print(f"Word count: {result['data']['pages'][0]['analysis']['content_analysis']['word_count']}")
```

## Recursive Scraping

To scrape multiple pages by following links:

```bash
scrapy recursive https://quotes.toscrape.com --depth 2 --limit 20
```

This will:
1. Start at the given URL
2. Follow links up to 2 levels deep
3. Scrape a maximum of 20 pages
4. Save all results to a single JSON file

## Using the Adaptive Scraper

The adaptive scraper automatically detects and extracts structured content:

```bash
scrapy adaptive https://quotes.toscrape.com --type list
```

This will:
1. Visit the specified URL
2. Detect content patterns (in this case, looking for list structures)
3. Extract structured data
4. Save the results as JSON

## Data Visualization

Generate a site map visualization from your scrape results:

```bash
scrapy viz sitemap ~/scrapy_output/recursive_quotes.toscrape.com_20230801_120000.json
```

Create a word cloud from the extracted text:

```bash
scrapy viz wordcloud ~/scrapy_output/scrape_quotes.toscrape.com_20230801_120000.json
```

## Using the Client Library

For more control, use the Python client library:

```python
from scrapy_client import ScrapyClient

# Initialize client
client = ScrapyClient(api_key="your_api_key")

# Perform an adaptive scrape
result = client.adaptive_scrape(
    url="https://quotes.toscrape.com",
    data_type="list",
    use_ai=True
)

# Process the results
for item in result['data']:
    print(f"Quote: {item['text']}")
    print(f"Author: {item['author']}")
    print("---")
```

## Next Steps

Now that you've completed your first scrapes, you can explore more advanced features:

1. Learn to [configure Scrapy](configuration.md) for your specific needs
2. Create more complex scrapers with the [Visual Builder](components/visual_builder.md)
3. Set up [scheduled scraping jobs](tools/scheduler.md) for regular updates
4. Explore [data visualization](visualization/content_analysis.md) options

For a complete exploration of Scrapy's capabilities, check out the [Core Components](components/webscraper.md) section.
