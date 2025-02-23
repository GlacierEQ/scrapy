from bs4 import BeautifulSoup
import json
import os
from collections import Counter
import re
from nltk.tokenize import word_tokenize, sent_tokenize
from nltk.corpus import stopwords
from nltk.probability import FreqDist
import nltk

class DataAnalyzer:
    def __init__(self):
        # Download required NLTK data
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt')
        try:
            nltk.data.find('corpora/stopwords')
        except LookupError:
            nltk.download('stopwords')

    def analyze_webpage(self, html_content):
        """
        Analyze webpage content and extract useful information
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        analysis = {
            "metadata": self.extract_metadata(soup),
            "content_analysis": self.analyze_content(soup),
            "structure_analysis": self.analyze_structure(soup),
            "link_analysis": self.analyze_links(soup),
            "text_statistics": self.analyze_text(soup)
        }
        
        return analysis

    def extract_metadata(self, soup):
        """Extract metadata from the webpage"""
        metadata = {
            "title": soup.title.string if soup.title else "",
            "meta_description": "",
            "meta_keywords": "",
            "charset": "",
            "language": ""
        }
        
        for meta in soup.find_all('meta'):
            if meta.get('name') == 'description':
                metadata['meta_description'] = meta.get('content', '')
            elif meta.get('name') == 'keywords':
                metadata['meta_keywords'] = meta.get('content', '')
            elif meta.get('charset'):
                metadata['charset'] = meta.get('charset')
        
        html_tag = soup.find('html')
        if html_tag and html_tag.get('lang'):
            metadata['language'] = html_tag.get('lang')
        
        return metadata

    def analyze_content(self, soup):
        """Analyze the content structure and composition"""
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        content = {
            "word_count": len(soup.get_text().split()),
            "headings": {
                f"h{i}": len(soup.find_all(f'h{i}'))
                for i in range(1, 7)
            },
            "paragraphs": len(soup.find_all('p')),
            "images": len(soup.find_all('img')),
            "lists": {
                "ordered": len(soup.find_all('ol')),
                "unordered": len(soup.find_all('ul'))
            }
        }
        
        return content

    def analyze_structure(self, soup):
        """Analyze the HTML structure"""
        structure = {
            "has_header": bool(soup.find('header')),
            "has_footer": bool(soup.find('footer')),
            "has_nav": bool(soup.find('nav')),
            "has_main": bool(soup.find('main')),
            "has_aside": bool(soup.find('aside')),
            "sections": len(soup.find_all('section')),
            "articles": len(soup.find_all('article')),
            "forms": len(soup.find_all('form')),
            "tables": len(soup.find_all('table'))
        }
        
        return structure

    def analyze_links(self, soup):
        """Analyze links in the webpage"""
        links = soup.find_all('a')
        
        link_analysis = {
            "total_links": len(links),
            "external_links": 0,
            "internal_links": 0,
            "social_media_links": 0,
            "email_links": 0
        }
        
        social_patterns = ['facebook.com', 'twitter.com', 'linkedin.com', 'instagram.com']
        
        for link in links:
            href = link.get('href', '')
            if href.startswith('mailto:'):
                link_analysis['email_links'] += 1
            elif href.startswith(('http://', 'https://')):
                link_analysis['external_links'] += 1
                if any(pattern in href.lower() for pattern in social_patterns):
                    link_analysis['social_media_links'] += 1
            elif href and not href.startswith('#'):
                link_analysis['internal_links'] += 1
        
        return link_analysis

    def analyze_text(self, soup):
        """Analyze text content"""
        text = soup.get_text()
        
        # Tokenize text
        sentences = sent_tokenize(text)
        words = word_tokenize(text.lower())
        
        # Remove stopwords and punctuation
        stop_words = set(stopwords.words('english'))
        words = [word for word in words if word.isalnum() and word not in stop_words]
        
        # Calculate word frequency
        fdist = FreqDist(words)
        
        statistics = {
            "sentence_count": len(sentences),
            "word_count": len(words),
            "avg_sentence_length": len(words) / len(sentences) if sentences else 0,
            "most_common_words": dict(fdist.most_common(10)),
            "vocabulary_size": len(set(words))
        }
        
        return statistics

    def save_analysis(self, analysis, output_path):
        """Save analysis results to a JSON file"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2)

    def generate_report(self, analysis):
        """Generate a human-readable report from the analysis"""
        report = []
        
        # Add metadata
        report.append("=== Page Metadata ===")
        report.append(f"Title: {analysis['metadata']['title']}")
        report.append(f"Description: {analysis['metadata']['meta_description']}")
        report.append(f"Language: {analysis['metadata']['language']}")
        
        # Add content statistics
        report.append("\n=== Content Statistics ===")
        report.append(f"Total Words: {analysis['content_analysis']['word_count']}")
        report.append("Headings:")
        for h_type, count in analysis['content_analysis']['headings'].items():
            if count > 0:
                report.append(f"  {h_type}: {count}")
        report.append(f"Images: {analysis['content_analysis']['images']}")
        
        # Add text analysis
        report.append("\n=== Text Analysis ===")
        report.append(f"Sentences: {analysis['text_statistics']['sentence_count']}")
        report.append(f"Average Sentence Length: {analysis['text_statistics']['avg_sentence_length']:.1f} words")
        report.append(f"Vocabulary Size: {analysis['text_statistics']['vocabulary_size']} unique words")
        
        # Add most common words
        report.append("\nMost Common Words:")
        for word, count in analysis['text_statistics']['most_common_words'].items():
            report.append(f"  {word}: {count}")
        
        # Add link analysis
        report.append("\n=== Link Analysis ===")
        report.append(f"Total Links: {analysis['link_analysis']['total_links']}")
        report.append(f"External Links: {analysis['link_analysis']['external_links']}")
        report.append(f"Internal Links: {analysis['link_analysis']['internal_links']}")
        report.append(f"Social Media Links: {analysis['link_analysis']['social_media_links']}")
        
        return "\n".join(report)

if __name__ == "__main__":
    analyzer = DataAnalyzer()
    with open('example.html', 'r', encoding='utf-8') as f:
        html_content = f.read()
    analysis = analyzer.analyze_webpage(html_content)
    print(analyzer.generate_report(analysis))
