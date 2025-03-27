"""
Test data generator for creating realistic test websites.

This module provides utilities to generate dynamic test websites with various
patterns commonly found on real websites, including product pages, article pages,
list pages, etc. for testing scrapers.
"""

import os
import random
import string
import json
from datetime import datetime, timedelta
import lorem
from typing import List, Dict, Any, Optional, Union, Tuple
from string import Template

# Templates for different types of pages
PAGE_TEMPLATES = {
    "product": Template("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${title} | ${store_name}</title>
    <meta name="description" content="${description}">
    <link rel="stylesheet" href="/styles/main.css">
    ${additional_meta}
</head>
<body>
    <header>
        <div class="logo">
            <a href="/"><img src="/images/logo.png" alt="${store_name}"></a>
        </div>
        <nav>
            <ul>
                ${nav_items}
            </ul>
        </nav>
    </header>
    <main>
        <div class="product-container">
            <div class="breadcrumbs">
                <a href="/">Home</a> > 
                <a href="/category/${category_slug}">${category_name}</a> > 
                <span>${title}</span>
            </div>
            <div class="product-page">
                <div class="product-images">
                    <div class="main-image">
                        <img src="${main_image}" alt="${title}">
                    </div>
                    <div class="thumbnails">
                        ${thumbnail_images}
                    </div>
                </div>
                <div class="product-info">
                    <h1 class="product-title">${title}</h1>
                    <div class="product-price ${sale_class}">
                        ${price_html}
                    </div>
                    <div class="product-rating">
                        ${rating_stars}
                        <span class="review-count">(${review_count} reviews)</span>
                    </div>
                    <div class="product-availability ${stock_class}">
                        ${availability_text}
                    </div>
                    <div class="product-description">
                        <p>${description}</p>
                    </div>
                    <div class="product-options">
                        ${product_options}
                    </div>
                    <div class="add-to-cart">
                        <button class="btn-quantity" id="decrease">-</button>
                        <input type="number" class="quantity" value="1" min="1" max="99">
                        <button class="btn-quantity" id="increase">+</button>
                        <button class="btn-primary add-to-cart-button">Add to Cart</button>
                    </div>
                </div>
            </div>
            <div class="product-details">
                <div class="tabs">
                    <button class="tab active" data-tab="specifications">Specifications</button>
                    <button class="tab" data-tab="features">Features</button>
                    <button class="tab" data-tab="reviews">Reviews</button>
                </div>
                <div id="specifications" class="tab-content active">
                    <h2>Specifications</h2>
                    <table class="specifications-table">
                        ${specifications_rows}
                    </table>
                </div>
                <div id="features" class="tab-content">
                    <h2>Features</h2>
                    <ul class="features-list">
                        ${features_list}
                    </ul>
                </div>
                <div id="reviews" class="tab-content">
                    <h2>Customer Reviews</h2>
                    ${reviews_content}
                </div>
            </div>
            <div class="related-products">
                <h2>Related Products</h2>
                <div class="products-grid">
                    ${related_products}
                </div>
            </div>
        </div>
    </main>
    <footer>
        <div class="footer-container">
            <div class="footer-section">
                <h3>About ${store_name}</h3>
                <p>${store_description}</p>
            </div>
            <div class="footer-section">
                <h3>Customer Service</h3>
                <ul>
                    <li><a href="/contact">Contact Us</a></li>
                    <li><a href="/shipping">Shipping Policy</a></li>
                    <li><a href="/returns">Returns & Refunds</a></li>
                    <li><a href="/faq">FAQ</a></li>
                </ul>
            </div>
            <div class="footer-section">
                <h3>Connect with Us</h3>
                <div class="social-icons">
                    <a href="#" class="social-icon"><i class="fab fa-facebook"></i></a>
                    <a href="#" class="social-icon"><i class="fab fa-twitter"></i></a>
                    <a href="#" class="social-icon"><i class="fab fa-instagram"></i></a>
                    <a href="#" class="social-icon"><i class="fab fa-pinterest"></i></a>
                </div>
            </div>
        </div>
        <div class="copyright">
            &copy; ${current_year} ${store_name}. All rights reserved.
        </div>
    </footer>
    <script src="/js/product.js"></script>
</body>
</html>
    """),
    
    "article": Template("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${title} | ${site_name}</title>
    <meta name="description" content="${description}">
    <link rel="stylesheet" href="/styles/main.css">
    ${additional_meta}
    <meta property="og:title" content="${title}">
    <meta property="og:description" content="${description}">
    <meta property="og:image" content="${main_image}">
    <meta property="og:type" content="article">
    <meta property="article:published_time" content="${published_date}">
    <meta property="article:author" content="${author_name}">
</head>
<body>
    <header>
        <div class="logo">
            <a href="/"><img src="/images/logo.png" alt="${site_name}"></a>
        </div>
        <nav>
            <ul>
                ${nav_items}
            </ul>
        </nav>
    </header>
    <main>
        <article class="blog-post">
            <div class="article-header">
                <div class="article-category">
                    <a href="/category/${category_slug}">${category_name}</a>
                </div>
                <h1 class="article-title">${title}</h1>
                <div class="article-meta">
                    <div class="author">
                        <img src="${author_image}" alt="${author_name}" class="author-image">
                        <div class="author-info">
                            <span class="author-name">By <a href="/author/${author_slug}">${author_name}</a></span>
                        </div>
                    </div>
                    <div class="publish-date">
                        <time datetime="${published_iso}">${published_date}</time>
                        ${modified_date_html}
                    </div>
                    <div class="article-stats">
                        <span class="reading-time">${reading_time} min read</span>
                        <span class="comment-count">${comment_count} comments</span>
                    </div>
                </div>
                <div class="featured-image">
                    <img src="${main_image}" alt="${image_alt}">
                    <div class="image-caption">${image_caption}</div>
                </div>
            </div>
            <div class="article-content">
                ${article_content}
            </div>
            <div class="article-tags">
                <span>Tags:</span>
                ${tags_html}
            </div>
            <div class="article-share">
                <span>Share:</span>
                <a href="#" class="share-button facebook">Facebook</a>
                <a href="#" class="share-button twitter">Twitter</a>
                <a href="#" class="share-button linkedin">LinkedIn</a>
                <a href="#" class="share-button email">Email</a>
            </div>
            <div class="author-bio">
                <img src="${author_image}" alt="${author_name}">
                <div>
                    <h3>${author_name}</h3>
                    <p>${author_bio}</p>
                    <div class="author-social">
                        ${author_social}
                    </div>
                </div>
            </div>
            <div class="article-comments">
                <h2>${comment_count} Comments</h2>
                ${comments_html}
            </div>
            <div class="related-articles">
                <h2>Related Articles</h2>
                <div class="articles-grid">
                    ${related_articles}
                </div>
            </div>
        </article>
        <aside class="sidebar">
            <div class="widget about-widget">
                <h3>About ${site_name}</h3>
                <p>${site_description}</p>
            </div>
            <div class="widget search-widget">
                <h3>Search</h3>
                <form class="search-form">
                    <input type="text" placeholder="Search...">
                    <button type="submit">Search</button>
                </form>
            </div>
            <div class="widget categories-widget">
                <h3>Categories</h3>
                <ul>
                    ${categories_list}
                </ul>
            </div>
            <div class="widget popular-posts-widget">
                <h3>Popular Posts</h3>
                <ul class="popular-posts">
                    ${popular_posts}
                </ul>
            </div>
        </aside>
    </main>
    <footer>
        <div class="footer-container">
            <div class="footer-section">
                <h3>About ${site_name}</h3>
                <p>${site_description}</p>
            </div>
            <div class="footer-section">
                <h3>Quick Links</h3>
                <ul>
                    <li><a href="/about">About Us</a></li>
                    <li><a href="/contact">Contact</a></li>
                    <li><a href="/privacy">Privacy Policy</a></li>
                    <li><a href="/terms">Terms of Service</a></li>
                </ul>
            </div>
            <div class="footer-section">
                <h3>Subscribe to Newsletter</h3>
                <form class="newsletter-form">
                    <input type="email" placeholder="Your Email Address">
                    <button type="submit">Subscribe</button>
                </form>
            </div>
        </div>
        <div class="copyright">
            &copy; ${current_year} ${site_name}. All rights reserved.
        </div>
    </footer>
    <script src="/js/article.js"></script>
</body>
</html>
    """),
    
    "listing": Template("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${title} | ${site_name}</title>
    <meta name="description" content="${description}">
    <link rel="stylesheet" href="/styles/main.css">
    ${additional_meta}
</head>
<body>
    <header>
        <div class="logo">
            <a href="/"><img src="/images/logo.png" alt="${site_name}"></a>
        </div>
        <nav>
            <ul>
                ${nav_items}
            </ul>
        </nav>
    </header>
    <main>
        <div class="listing-header">
            <h1>${title}</h1>
            <div class="breadcrumbs">
                <a href="/">Home</a> > 
                ${breadcrumb_path}
            </div>
            <div class="listing-description">
                <p>${description}</p>
            </div>
        </div>
        <div class="listing-container">
            <div class="filters">
                <div class="filter-section">
                    <h3>Sort By</h3>
                    <select class="sort-options">
                        <option value="popularity">Most Popular</option>
                        <option value="price-asc">Price: Low to High</option>
                        <option value="price-desc">Price: High to Low</option>
                        <option value="newest">Newest First</option>
                    </select>
                </div>
                ${filter_sections}
            </div>
            <div class="listing-results">
                <div class="result-count">
                    <p>Showing ${result_range} of ${total_results} results</p>
                </div>
                <div class="view-options">
                    <button class="view-option grid active"><i class="fas fa-th"></i></button>
                    <button class="view-option list"><i class="fas fa-list"></i></button>
                </div>
                <div class="results-grid">
                    ${listing_items}
                </div>
                <div class="pagination">
                    ${pagination_html}
                </div>
            </div>
        </div>
    </main>
    <footer>
        <div class="footer-container">
            <div class="footer-section">
                <h3>About ${site_name}</h3>
                <p>${site_description}</p>
            </div>
            <div class="footer-section">
                <h3>Customer Service</h3>
                <ul>
                    <li><a href="/contact">Contact Us</a></li>
                    <li><a href="/shipping">Shipping</a></li>
                    <li><a href="/returns">Returns</a></li>
                    <li><a href="/faq">FAQ</a></li>
                </ul>
            </div>
            <div class="footer-section">
                <h3>Connect with Us</h3>
                <div class="social-icons">
                    <a href="#" class="social-icon"><i class="fab fa-facebook"></i></a>
                    <a href="#" class="social-icon"><i class="fab fa-twitter"></i></a>
                    <a href="#" class="social-icon"><i class="fab fa-instagram"></i></a>
                    <a href="#" class="social-icon"><i class="fab fa-pinterest"></i></a>
                </div>
            </div>
        </div>
        <div class="copyright">
            &copy; ${current_year} ${site_name}. All rights reserved.
        </div>
    </footer>
    <script src="/js/listing.js"></script>
</body>
</html>
    """)
}

class TestDataGenerator:
    """Generator for realistic test websites for scraper development and testing."""
    
    def __init__(self, output_dir: str):
        """
        Initialize the test data generator.
        
        Args:
            output_dir: Directory to output generated websites
        """
        self.output_dir = output_dir
        self.current_year = datetime.now().year
        self.rng = random.Random(42)  # Use fixed seed for reproducibility
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
    def generate_product_site(
        self, 
        site_name: str = "TestShop", 
        num_products: int = 20, 
        num_categories: int = 5,
        output_path: Optional[str] = None
    ) -> str:
        """
        Generate a test e-commerce website.
        
        Args:
            site_name: Name of the test shop
            num_products: Number of products to generate
            num_categories: Number of categories
            output_path: Custom output path (default: output_dir/site_name)
            
        Returns:
            Path to the generated website directory
        """
        # Create site directory
        if not output_path:
            output_path = os.path.join(self.output_dir, self._slugify(site_name))
        
        os.makedirs(output_path, exist_ok=True)
        
        # Create directory structure
        for subdir in ['images', 'css', 'js', 'category', 'product']:
            os.makedirs(os.path.join(output_path, subdir), exist_ok=True)
        
        # Generate site metadata
        site_data = {
            'name': site_name,
            'description': f"{site_name} is a fictional store created for testing web scrapers.",
            'url': f"https://example.com/{self._slugify(site_name)}",
            'categories': self._generate_categories(num_categories),
            'products': [],
        }
        
        # Generate products
        for i in range(num_products):
            product = self._generate_product(site_data['categories'])
            site_data['products'].append(product)
            
            # Create product page
            product_path = os.path.join(output_path, 'product', f"{product['slug']}.html")
            with open(product_path, 'w', encoding='utf-8') as f:
                f.write(self._render_product_page(product, site_data))
        
        # Create category pages
        for category in site_data['categories']:
            category_products = [p for p in site_data['products'] if p['category_id'] == category['id']]
            category_path = os.path.join(output_path, 'category', f"{category['slug']}.html")
            with open(category_path, 'w', encoding='utf-8') as f:
                f.write(self._render_category_page(category, category_products, site_data))
        
        # Create index page with featured products
        index_path = os.path.join(output_path, 'index.html')
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(self._render_index_page(site_data))
            
        # Save site metadata
        with open(os.path.join(output_path, 'site_data.json'), 'w', encoding='utf-8') as f:
            json.dump(site_data, f, indent=2)
            
        return output_path
    
    def generate_blog_site(
        self, 
        site_name: str = "TestBlog", 
        num_articles: int = 15, 
        num_categories: int = 5,
        output_path: Optional[str] = None
    ) -> str:
        """
        Generate a test blog website.
        
        Args:
            site_name: Name of the test blog
            num_articles: Number of articles to generate
            num_categories: Number of categories
            output_path: Custom output path (default: output_dir/site_name)
            
        Returns:
            Path to the generated website directory
        """
        # Create site directory
        if not output_path:
            output_path = os.path.join(self.output_dir, self._slugify(site_name))
        
        os.makedirs(output_path, exist_ok=True)
        
        # Create directory structure
        for subdir in ['images', 'css', 'js', 'category', 'author', 'article']:
            os.makedirs(os.path.join(output_path, subdir), exist_ok=True)
        
        # Generate site metadata
        site_data = {
            'name': site_name,
            'description': f"{site_name} is a fictional blog created for testing web scrapers.",
            'url': f"https://example.com/{self._slugify(site_name)}",
            'categories': self._generate_categories(num_categories),
            'authors': self._generate_authors(3),  # Generate 3 authors
            'articles': [],
        }
        
        # Generate articles
        for i in range(num_articles):
            article = self._generate_article(site_data['categories'], site_data['authors'])
            site_data['articles'].append(article)
            
            # Create article page
            article_path = os.path.join(output_path, 'article', f"{article['slug']}.html")
            with open(article_path, 'w', encoding='utf-8') as f:
                f.write(self._render_article_page(article, site_data))
        
        # Create category pages
        for category in site_data['categories']:
            category_articles = [a for a in site_data['articles'] if a['category_id'] == category['id']]
            category_path = os.path.join(output_path, 'category', f"{category['slug']}.html")
            with open(category_path, 'w', encoding='utf-8') as f:
                f.write(self._render_category_articles_page(category, category_articles, site_data))
        
        # Create author pages
        for author in site_data['authors']:
            author_articles = [a for a in site_data['articles'] if a['author_id'] == author['id']]
            author_path = os.path.join(output_path, 'author', f"{author['slug']}.html")
            with open(author_path, 'w', encoding='utf-8') as f:
                f.write(self._render_author_page(author, author_articles, site_data))
        
        # Create index page with latest articles
        index_path = os.path.join(output_path, 'index.html')
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(self._render_blog_index_page(site_data))
            
        # Save site metadata
        with open(os.path.join(output_path, 'site_data.json'), 'w', encoding='utf-8') as f:
            json.dump(site_data, f, indent=2)
            
        return output_path
    
    def _generate_product(self, categories: List[Dict]) -> Dict[str, Any]:
        """Generate a single product."""
        category = self.rng.choice(categories)
        product_id = self._generate_id()
        title = f"{self.rng.choice(['Premium', 'Deluxe', 'Professional', 'Classic', 'Modern'])} {category['name']} {self.rng.choice(['Pro', 'Plus', 'Max', 'Ultra', ''])}"
        price = round(self.rng.uniform(9.99, 999.99), 2)
        on_sale = self.rng.random() < 0.3  # 30% chance of being on sale
        
        if on_sale:
            sale_price = round(price * (1 - self.rng.uniform(0.1, 0.4)), 2)  # 10-40% off
        else:
            sale_price = None
        
        # Generate specifications
        num_specs = self.rng.randint(3, 8)
        specs = {}
        for _ in range(num_specs):
            key = self.rng.choice([
                'Weight', 'Dimensions', 'Material', 'Color', 'Battery Life',
                'Warranty', 'Model Number', 'Compatibility', 'Country of Origin',
                'Connectivity', 'Power Source', 'Capacity', 'Resolution'
            ])
            if key not in specs:  # Avoid duplicates
                specs[key] = self._generate_spec_value(key)
        
        # Generate features
        num_features = self.rng.randint(3, 6)
        features = []
        for _ in range(num_features):
            features.append(lorem.sentence())
        
        # Generate stock status
        in_stock = self.rng.random() < 0.8  # 80% chance of being in stock
        if in_stock:
            stock_quantity = self.rng.randint(1, 100)
        else:
            stock_quantity = 0
        
        # Generate rating
        rating = round(self.rng.uniform(3.0, 5.0), 1)
        review_count = self.rng.randint(0, 50)
        
        return {
            'id': product_id,
            'title': title,
            'slug': self._slugify(title),
            'category_id': category['id'],
            'category_name': category['name'],
            'category_slug': category['slug'],
            'description': lorem.paragraph(),
            'price': price,
            'sale_price': sale_price,
            'currency': '$',
            'stock_quantity': stock_quantity,
            'in_stock': in_stock,
            'specifications': specs,
            'features': features,
            'rating': rating,
            'review_count': review_count,
            'image': f"/images/product-{product_id}.jpg",
            'thumbnail': f"/images/product-{product_id}-thumb.jpg",
            'gallery': [f"/images/product-{product_id}-gallery-{i}.jpg" for i in range(1, 4)]
        }
    
    def _generate_article(self, categories: List[Dict], authors: List[Dict]) -> Dict[str, Any]:
        """Generate a single blog article."""
        category = self.rng.choice(categories)
        author = self.rng.choice(authors)
        article_id = self._generate_id()
        
        # Generate title
        title_templates = [
            "The Ultimate Guide to ${topic}",
            "${number} Ways to Improve Your ${topic}",
            "How to ${action} Your ${topic} in ${timeframe}",
            "Why ${topic} Matters More Than You Think",
            "${topic}: A Comprehensive Analysis",
            "The Future of ${topic} in ${year}",
            "What Nobody Tells You About ${topic}",
            "${number} ${topic} Trends to Watch in ${year}"
        ]
        
        template = self.rng.choice(title_templates)
        title = Template(template).substitute(
            topic=self.rng.choice(['Marketing', 'Technology', 'Business', 'Design', 'Development', 'Leadership', 'Innovation']),
            number=self.rng.choice(['5', '7', '10', '12', '15']),
            action=self.rng.choice(['Boost', 'Transform', 'Optimize', 'Improve', 'Revamp']),
            timeframe=self.rng.choice(['30 Days', 'One Week', 'Two Months', '24 Hours']),
            year=str(self.current_year + self.rng.randint(0, 5))
        )
        
        # Generate publish date (within the last year)
        days_ago = self.rng.randint(0, 365)
        published_date = datetime.now() - timedelta(days=days_ago)
        
        # 30% chance of having a modified date
        if self.rng.random() < 0.3:
            modified_days_ago = self.rng.randint(0, days_ago)
            modified_date = datetime.now() - timedelta(days=modified_days_ago)
        else:
            modified_date = None
        
        # Generate content
        paragraphs = []
        num_paragraphs = self.rng.randint(4, 10)
        
        # Add heading and paragraphs
        for i in range(num_paragraphs):
            if i > 0 and self.rng.random() < 0.3:  # 30% chance of a heading
                paragraphs.append({
                    'type': 'heading',
                    'level': self.rng.randint(2, 3),
                    'text': lorem.sentence().rstrip('.')
                })
            
            paragraphs.append({
                'type': 'paragraph',
                'text': lorem.paragraph()
            })
            
            # Maybe add an image
            if self.rng.random() < 0.2:  # 20% chance of an image
                paragraphs.append({
                    'type': 'image',
                    'src': f"/images/article-{article_id}-content-{i}.jpg",
                    'alt': lorem.sentence(),
                    'caption': lorem.sentence() if self.rng.random() < 0.7 else None
                })
            
            # Maybe add a blockquote
            if self.rng.random() < 0.1:  # 10% chance of a blockquote
                paragraphs.append({
                    'type': 'blockquote',
                    'text': lorem.paragraph()
                })
        
        # Generate tags
        num_tags = self.rng.randint(2, 6)
        all_tags = ['Technology', 'Business', 'Marketing', 'Design', 'Development', 
                    'Leadership', 'Innovation', 'Strategy', 'Growth', 'Analytics',
                    'Social Media', 'Content', 'SEO', 'Product', 'Customer Experience']
        tags = self.rng.sample(all_tags, min(num_tags, len(all_tags)))
        
        # Generate word count and reading time
        word_count = sum(len(p['text'].split()) for p in paragraphs if p['type'] in ['paragraph', 'blockquote'])
        reading_time = max(1, round(word_count / 200))  # Assuming 200 words per minute
        
        # Generate comments
        num_comments = self.rng.randint(0, 10)
        comments = []
        
        for _ in range(num_comments):
            days_since_publish = self.rng.randint(0, days_ago)
            comment_date = published_date + timedelta(days=days_since_publish)
            
            comments.append({
                'author_name': f"{self.rng.choice(['John', 'Jane', 'Mike', 'Sarah', 'David', 'Lisa'])} {self.rng.choice(['Smith', 'Johnson', 'Williams', 'Jones', 'Brown', 'Davis'])}",
                'author_email': f"user{self.rng.randint(1, 999)}@example.com",
                'date': comment_date.strftime('%Y-%m-%d'),
                'text': lorem.paragraph(),
                'replies': []  # Could add nested replies here
            })
        
        return {
            'id': article_id,
            'title': title,
            'slug': self._slugify(title),
            'category_id': category['id'],
            'category_name': category['name'],
            'category_slug': category['slug'],
            'author_id': author['id'],
            'author_name': author['name'],
            'author_slug': author['