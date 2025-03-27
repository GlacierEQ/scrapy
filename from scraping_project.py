from scraping_project.general_webscraper import WebpageScraper
import argparse

def main():
    parser = argparse.ArgumentParser(description="Webpage scraper tool")
    parser.add_argument("url", help="URL to scrape")
    parser.add_argument("-o", "--output", default="output", help="Directory for output")
    parser.add_argument("--follow", action="store_true", help="Follow links on the page")
    parser.add_argument("--compile", action="store_true", help="Compile text analysis for pages")
    parser.add_argument("--max_pages", type=int, default=10, help="Maximum number of pages to scrape")
    args = parser.parse_args()

    scraper = WebpageScraper(args.output)
    result = scraper.save_webpage(
        url=args.url,
        follow_links=args.follow,
        compile_text=args.compile,
        max_pages=args.max_pages
    )
    print(result)

if __name__ == "__main__":
    main()
