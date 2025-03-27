"""
Data Visualization Module for Scrapy.

This module provides tools for visualizing and analyzing scraped data
through charts, graphs, and interactive visualizations.
"""

import os
import json
import logging
import math
from typing import Dict, List, Any, Optional, Tuple, Union, Set
from datetime import datetime
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from wordcloud import WordCloud
from matplotlib.ticker import MaxNLocator
import networkx as nx
from collections import Counter, defaultdict
from bs4 import BeautifulSoup
import re

# Optional imports for interactive visualizations
try:
    import plotly.express as px
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

# Setup logging
logger = logging.getLogger(__name__)

class ScrapyVisualizer:
    """
    Data visualization tools for Scrapy output.
    
    This class provides methods for creating visualizations from scraped data,
    including charts, graphs, site maps, and word frequency analyses.
    """
    
    def __init__(self, 
                output_dir: Optional[str] = None,
                style: str = 'darkgrid',
                color_palette: str = 'viridis',
                fig_size: Tuple[int, int] = (12, 8),
                dpi: int = 100,
                interactive: bool = True):
        """
        Initialize the visualizer.
        
        Args:
            output_dir: Directory to save visualizations
            style: Seaborn style name
            color_palette: Color palette to use
            fig_size: Default figure size (width, height)
            dpi: Default figure DPI
            interactive: Whether to use interactive visualizations when possible
        """
        self.output_dir = output_dir or os.path.join(os.getcwd(), 'visualizations')
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.style = style
        self.color_palette = color_palette
        self.fig_size = fig_size
        self.dpi = dpi
        self.interactive = interactive and PLOTLY_AVAILABLE
        
        # Set up styling
        sns.set_style(style)
        sns.set_palette(color_palette)
        plt.rcParams['figure.figsize'] = fig_size
        plt.rcParams['figure.dpi'] = dpi
    
    def load_data(self, input_path: str) -> Dict[str, Any]:
        """
        Load scraped data from a JSON file.
        
        Args:
            input_path: Path to the JSON file
            
        Returns:
            Loaded data
        """
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        except Exception as e:
            logger.error(f"Error loading data from {input_path}: {e}")
            raise
    
    def convert_to_dataframe(self, data: Dict[str, Any]) -> pd.DataFrame:
        """
        Convert scraped data to a pandas DataFrame.
        
        Args:
            data: Scraped data
            
        Returns:
            DataFrame representation
        """
        # Check for pages array pattern
        if "data" in data and "pages" in data["data"]:
            # Convert list of pages to DataFrame
            pages = data["data"]["pages"]
            df = pd.json_normalize(pages)
            return df
        
        # For adaptive scraper outputs with data arrays
        elif "data" in data and isinstance(data["data"], list):
            # Normalize list of records
            df = pd.json_normalize(data["data"])
            return df
        
        # For simple key-value data
        elif "data" in data and isinstance(data["data"], dict):
            # Try to normalize a nested dictionary
            try:
                df = pd.json_normalize(data["data"])
            except Exception:
                # Fallback to simple Series conversion
                df = pd.DataFrame([data["data"]])
            return df
        
        # Direct data structure (for API outputs)
        elif isinstance(data, list):
            df = pd.json_normalize(data)
            return df
        
        # Fall back to creating a DataFrame from the entire structure
        df = pd.json_normalize(data)
        return df
    
    def create_site_map(self, 
                       data: Dict[str, Any],
                       title: str = "Website Structure",
                       save_path: Optional[str] = None,
                       show_domains: bool = True,
                       layout: str = "spring") -> Optional[plt.Figure]:
        """
        Create a site map visualization from crawl data.
        
        Args:
            data: Scraped data
            title: Chart title
            save_path: Path to save the visualization
            show_domains: Highlight different domains with colors
            layout: Network layout algorithm
            
        Returns:
            Generated figure
        """
        # Check if data has pages
        if "data" not in data or "pages" not in data["data"]:
            logger.error("Data does not contain pages structure")
            return None
        
        # Extract pages
        pages = data["data"]["pages"]
        
        # Create a directed graph
        G = nx.DiGraph()
        
        # Extract all unique URLs
        all_urls = set()
        url_to_title = {}
        url_to_domain = {}
        
        # First pass: collect nodes
        for page in pages:
            url = page.get("url", "")
            if not url:
                continue
                
            all_urls.add(url)
            url_to_title[url] = page.get("title", url)
            
            # Extract domain
            domain = self._extract_domain(url)
            url_to_domain[url] = domain
            
            # Add node
            G.add_node(url, title=page.get("title", ""), domain=domain)
        
        # Second pass: add edges
        for page in pages:
            source_url = page.get("url", "")
            if not source_url or source_url not in all_urls:
                continue
            
            # Check if the page has links
            if "links" in page:
                for link in page["links"]:
                    target_url = link.get("href", "")
                    if target_url and target_url in all_urls:
                        G.add_edge(source_url, target_url)
        
        # Create figure
        plt.figure(figsize=self.fig_size, dpi=self.dpi)
        plt.title(title)
        
        # Create position layout
        pos = getattr(nx, f"{layout}_layout")(G)
        
        # Prepare node colors by domain if requested
        if show_domains:
            domains = list(set(url_to_domain.values()))
            domain_colors = {}
            cmap = plt.cm.get_cmap(self.color_palette, len(domains))
            
            for i, domain in enumerate(domains):
                domain_colors[domain] = cmap(i)
            
            node_colors = [domain_colors[url_to_domain[url]] for url in G.nodes()]
        else:
            node_colors = 'skyblue'
        
        # Draw the network
        nx.draw_networkx(
            G,
            pos=pos,
            with_labels=False,
            node_color=node_colors,
            node_size=100,
            alpha=0.8,
            arrows=True,
            edge_color='gray',
            width=0.5
        )
        
        # Add tooltips for interactive mode
        annotations = []
        for node, (x, y) in pos.items():
            title = url_to_title.get(node, node)
            annotations.append((x, y, title[:30] + "..." if len(title) > 30 else title))
        
        # Save if requested
        if save_path:
            full_path = os.path.join(self.output_dir, save_path)
            plt.savefig(full_path, bbox_inches='tight')
            plt.close()
            logger.info(f"Site map saved to {full_path}")
        
        return plt.gcf()
    
    def create_interactive_site_map(self, 
                                  data: Dict[str, Any],
                                  title: str = "Interactive Website Structure",
                                  save_path: Optional[str] = None) -> Optional[Any]:
        """
        Create an interactive site map visualization using Plotly.
        
        Args:
            data: Scraped data
            title: Chart title
            save_path: Path to save the visualization
            
        Returns:
            Plotly figure
        """
        if not PLOTLY_AVAILABLE:
            logger.warning("Plotly is not available. Please install plotly to use interactive visualizations.")
            return None
        
        # Check if data has pages
        if "data" not in data or "pages" not in data["data"]:
            logger.error("Data does not contain pages structure")
            return None
        
        # Extract pages
        pages = data["data"]["pages"]
        
        # Create a directed graph
        G = nx.DiGraph()
        
        # Extract all unique URLs
        all_urls = set()
        url_to_title = {}
        url_to_domain = {}
        
        # First pass: collect nodes
        for page in pages:
            url = page.get("url", "")
            if not url:
                continue
                
            all_urls.add(url)
            url_to_title[url] = page.get("title", url)
            
            # Extract domain
            domain = self._extract_domain(url)
            url_to_domain[url] = domain
            
            # Add node
            G.add_node(url, title=page.get("title", ""), domain=domain)
        
        # Second pass: add edges
        edges = []
        for page in pages:
            source_url = page.get("url", "")
            if not source_url or source_url not in all_urls:
                continue
            
            # Check if the page has links
            if "links" in page:
                for link in page["links"]:
                    target_url = link.get("href", "")
                    if target_url and target_url in all_urls:
                        G.add_edge(source_url, target_url)
                        edges.append((source_url, target_url))
        
        # Use networkx to compute positions
        pos = nx.spring_layout(G)
        
        # Prepare node colors by domain
        domains = list(set(url_to_domain.values()))
        domain_to_idx = {domain: i for i, domain in enumerate(domains)}
        node_colors = [domain_to_idx[url_to_domain[node]] for node in G.nodes()]
        
        # Create edge traces
        edge_x = []
        edge_y = []
        
        for edge in G.edges():
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])
        
        edge_trace = go.Scatter(
            x=edge_x, y=edge_y,
            line=dict(width=0.5, color='#888'),
            hoverinfo='none',
            mode='lines')
        
        # Create node traces
        node_x = []
        node_y = []
        node_text = []
        node_domain = []
        
        for node in G.nodes():
            x, y = pos[node]
            node_x.append(x)
            node_y.append(y)
            node_text.append(url_to_title.get(node, node))
            node_domain.append(url_to_domain[node])
        
        node_trace = go.Scatter(
            x=node_x, y=node_y,
            mode='markers',
            hoverinfo='text',
            text=node_text,
            marker=dict(
                showscale=True,
                colorscale=self.color_palette,
                color=node_colors,
                size=10,
                colorbar=dict(
                    thickness=15,
                    title='Domain',
                    xanchor='left',
                    titleside='right'
                ),
                line_width=2))
        
        # Create figure
        fig = go.Figure(data=[edge_trace, node_trace],
             layout=go.Layout(
                title=title,
                titlefont_size=16,
                showlegend=False,
                hovermode='closest',
                margin=dict(b=20,l=5,r=5,t=40),
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False))
                )
        
        # Save if requested
        if save_path:
            full_path = os.path.join(self.output_dir, save_path)
            fig.write_html(full_path)
            logger.info(f"Interactive site map saved to {full_path}")
        
        return fig
    
    def create_word_cloud(self, 
                        data: Dict[str, Any],
                        text_field: str = "text",
                        title: str = "Word Frequency",
                        save_path: Optional[str] = None,
                        width: int = 800,
                        height: int = 400,
                        max_words: int = 200,
                        background_color: str = "white") -> Optional[plt.Figure]:
        """
        Create a word cloud visualization from extracted text.
        
        Args:
            data: Scraped data
            text_field: Field containing text to analyze
            title: Chart title
            save_path: Path to save the visualization
            width: Width of word cloud
            height: Height of word cloud
            max_words: Maximum words to include
            background_color: Background color
            
        Returns:
            Generated figure
        """
        # Convert data to DataFrame for easier access
        df = self.convert_to_dataframe(data)
        
        # Check if text field exists
        if text_field not in df.columns:
            logger.error(f"Text field '{text_field}' not found in data")
            
            # Try to find alternative text fields
            text_columns = [col for col in df.columns if any(substr in col.lower() for substr in ['text', 'content', 'body', 'description'])]
            
            if text_columns:
                text_field = text_columns[0]
                logger.info(f"Using alternative text field: {text_field}")
            else:
                return None
        
        # Combine all text
        all_text = " ".join(df[text_field].astype(str).tolist())
        
        # Create word cloud
        wordcloud = WordCloud(
            width=width,
            height=height,
            max_words=max_words,
            background_color=background_color,
            colormap=self.color_palette
        ).generate(all_text)
        
        # Create figure
        plt.figure(figsize=self.fig_size)
        plt.imshow(wordcloud, interpolation='bilinear')
        plt.axis('off')
        plt.title(title)
        plt.tight_layout(pad=0)
        
        # Save if requested
        if save_path:
            full_path = os.path.join(self.output_dir, save_path)
            plt.savefig(full_path, bbox_inches='tight')
            logger.info(f"Word cloud saved to {full_path}")
        
        return plt.gcf()
    
    def create_content_analysis_dashboard(self, 
                                        data: Dict[str, Any],
                                        save_path: Optional[str] = None) -> Optional[Any]:
        """
        Create a comprehensive dashboard with content metrics.
        
        Args:
            data: Scraped data
            save_path: Path to save the dashboard
            
        Returns:
            Dashboard figure
        """
        if not PLOTLY_AVAILABLE:
            logger.warning("Plotly is not available for interactive dashboard. Using static plots.")
            return self.create_content_analysis_static(data, save_path)
        
        # Convert to DataFrame
        df = self.convert_to_dataframe(data)
        
        # Prepare metrics depending on columns
        metrics = []
        
        # Look for common content analysis fields
        analysis_cols = {
            'word_count': ['word_count', 'wordCount', 'word count', 'words'],
            'sentence_count': ['sentence_count', 'sentenceCount', 'sentence count', 'sentences'],
            'paragraph_count': ['paragraph_count', 'paragraphCount', 'paragraph count', 'paragraphs'],
            'readability_score': ['readability_score', 'readabilityScore', 'readability', 'flesch_score'],
            'load_time': ['load_time', 'loadTime', 'time', 'duration', 'load_duration']
        }
        
        # Find the actual column names in the dataframe
        metrics_found = {}
        for metric_key, possible_cols in analysis_cols.items():
            for col in possible_cols:
                if any(c == col or c.endswith('.' + col) for c in df.columns):
                    matching_col = next(c for c in df.columns if c == col or c.endswith('.' + col))
                    metrics_found[metric_key] = matching_col
                    break
        
        # Create dashboard with subplots
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=("Word Count Distribution", "Readability Scores", 
                           "Content Length vs. Reading Time", "Top Domains"),
            specs=[[{"type": "histogram"}, {"type": "box"}],
                  [{"type": "scatter"}, {"type": "bar"}]]
        )
        
        # Add word count histogram
        if 'word_count' in metrics_found:
            word_counts = df[metrics_found['word_count']].dropna()
            fig.add_trace(
                go.Histogram(
                    x=word_counts,
                    nbinsx=20,
                    marker_color='rgba(110, 220, 200, 0.7)',
                    name="Word Counts"
                ),
                row=1, col=1
            )
            
            # Set axis title
            fig.update_xaxes(title_text="Word Count", row=1, col=1)
            fig.update_yaxes(title_text="Frequency", row=1, col=1)
        
        # Add readability box plot
        if 'readability_score' in metrics_found:
            readability = df[metrics_found['readability_score']].dropna()
            fig.add_trace(
                go.Box(
                    y=readability,
                    name="Readability",
                    marker_color='rgba(220, 110, 200, 0.7)'
                ),
                row=1, col=2
            )
            
            # Set axis title
            fig.update_yaxes(title_text="Readability Score", row=1, col=2)
        
        # Add scatter plot for content length vs reading time
        if 'word_count' in metrics_found:
            word_counts = df[metrics_found['word_count']].dropna()
            
            # Estimate reading time (5 words per second is about 300 words per minute)
            reading_time = word_counts / 300 * 60  # in seconds
            
            fig.add_trace(
                go.Scatter(
                    x=word_counts,
                    y=reading_time,
                    mode='markers',
                    marker=dict(
                        size=8,
                        color=reading_time,
                        colorscale='Viridis',
                        showscale=True
                    ),
                    name="Reading Time"
                ),
                row=2, col=1
            )
            
            # Set axis titles
            fig.update_xaxes(title_text="Word Count", row=2, col=1)
            fig.update_yaxes(title_text="Est. Reading Time (sec)", row=2, col=1)
        
        # Add domain bar chart
        url_col = next((c for c in df.columns if 'url' in c.lower()), None)
        if url_col:
            # Extract domains
            domains = df[url_col].apply(self._extract_domain)
            domain_counts = domains.value_counts().head(10)
            
            fig.add_trace(
                go.Bar(
                    x=domain_counts.index,
                    y=domain_counts.values,
                    marker_color='rgba(110, 110, 220, 0.7)',
                    name="Domains"
                ),
                row=2, col=2
            )
            
            # Set axis titles
            fig.update_xaxes(title_text="Domain", row=2, col=2, tickangle=45)
            fig.update_yaxes(title_text="Count", row=2, col=2)
        
        # Update layout
        fig.update_layout(
            title="Content Analysis Dashboard",
            height=800,
            showlegend=False
        )
        
        # Save if requested
        if save_path:
            full_path = os.path.join(self.output_dir, save_path)
            fig.write_html(full_path)
            logger.info(f"Content analysis dashboard saved to {full_path}")
        
        return fig
    
    def create_content_analysis_static(self, 
                                     data: Dict[str, Any],
                                     save_path: Optional[str] = None) -> Optional[plt.Figure]:
        """
        Create a static content analysis dashboard.
        
        Args:
            data: Scraped data
            save_path: Path to save the dashboard
            
        Returns:
            Dashboard figure
        """
        # Convert to DataFrame
        df = self.convert_to_dataframe(data)
        
        # Look for common content analysis fields
        analysis_cols = {
            'word_count': ['word_count', 'wordCount', 'word count', 'words'],
            'sentence_count': ['sentence_count', 'sentenceCount', 'sentence count', 'sentences'],
            'paragraph_count': ['paragraph_count', 'paragraphCount', 'paragraph count', 'paragraphs'],
            'readability_score': ['readability_score', 'readabilityScore', 'readability', 'flesch_score'],
            'load_time': ['load_time', 'loadTime', 'time', 'duration', 'load_duration']
        }
        
        # Find the actual column names in the dataframe
        metrics_found = {}
        for metric_key, possible_cols in analysis_cols.items():
            for col in possible_cols:
                if any(c == col or c.endswith('.' + col) for c in df.columns):
                    matching_col = next(c for c in df.columns if c == col or c.endswith('.' + col))
                    metrics_found[metric_key] = matching_col
                    break
        
        # Create a figure with subplots
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle("Content Analysis Dashboard", fontsize=16)
        
        # Plot word count histogram
        if 'word_count' in metrics_found:
            word_counts = df[metrics_found['word_count']].dropna()
            axes[0, 0].hist(word_counts, bins=20, color='skyblue', alpha=0.7)
            axes[0, 0].set_title("Word Count Distribution")
            axes[0, 0].set_xlabel("Word Count")
            axes[0, 0].set_ylabel("Frequency")
            axes[0, 0].grid(True, alpha=0.3)
        else:
            axes[0, 0].text(0.5, 0.5, "Word count data not available", 
                          horizontalalignment='center', verticalalignment='center')
        
        # Plot readability scores
        if 'readability_score' in metrics_found:
            readability = df[metrics_found['readability_score']].dropna()
            axes[0, 1].boxplot(readability, vert=True, patch_artist=True, 
                             boxprops=dict(facecolor='lightgreen', alpha=0.7))
            axes[0, 1].set_title("Readability Scores")
            axes[0, 1].set_ylabel("Readability Score")
            axes[0, 1].grid(True, alpha=0.3)
        else:
            axes[0, 1].text(0.5, 0.5, "Readability data not available", 
                          horizontalalignment='center', verticalalignment='center')
        
        # Plot word count vs reading time scatter
        if 'word_count' in metrics_found:
            word_counts = df[metrics_found['word_count']].dropna()
            reading_time = word_counts / 300 * 60  # 300 words per minute
            
            scatter = axes[1, 0].scatter(word_counts, reading_time, alpha=0.7, 
                                       c=reading_time, cmap='viridis')
            axes[1, 0].set_title("Content Length vs. Reading Time")
            axes[1, 0].set_xlabel("Word Count")
            axes[1, 0].set_ylabel("Est. Reading Time (sec)")
            axes[1, 0].grid(True, alpha=0.3)
            plt.colorbar(scatter, ax=axes[1, 0])
        else:
            axes[1, 0].text(0.5, 0.5, "Word count data not available", 
                          horizontalalignment='center', verticalalignment='center')
        
        # Plot domain counts
        url_col = next((c for c in df.columns if 'url' in c.lower()), None)
        if url_col:
            domains = df[url_col].apply(self._extract_domain)
            domain_counts = domains.value_counts().head(10)
            
            x = np.arange(len(domain_counts))
            axes[1, 1].bar(x, domain_counts.values, color='coral', alpha=0.7)
            axes[1, 1].set_title("Top Domains")
            axes[1, 1].set_xticks(x)
            axes[1, 1].set_xticklabels(domain_counts.index, rotation=45, ha='right')
            axes[1, 1].set_ylabel("Count")
            axes[1, 1].grid(True, alpha=0.3)
        else:
            axes[1, 1].text(0.5, 0.5, "URL data not available", 
                          horizontalalignment='center', verticalalignment='center')
        
        plt.tight_layout()
        plt.subplots_adjust(top=0.92)
        
        # Save if requested
        if save_path:
            full_path = os.path.join(self.output_dir, save_path)
            plt.savefig(full_path, bbox_inches='tight')
            logger.info(f"Content analysis dashboard saved to {full_path}")
        
        return fig
    
    def create_link_analysis(self, 
                           data: Dict[str, Any],
                           save_path: Optional[str] = None) -> Optional[Union[plt.Figure, Any]]:
        """
        Create link analysis visualization.
        
        Args:
            data: Scraped data
            save_path: Path to save the visualization
            
        Returns:
            Link analysis figure
        """
        # Use interactive if available
        if self.interactive and PLOTLY_AVAILABLE:
            return self._create_interactive_link_analysis(data, save_path)
        else:
            return self._create_static_link_analysis(data, save_path)
    
    def _create_interactive_link_analysis(self, data: Dict[str, Any], save_path: Optional[str] = None) -> Optional[Any]:
        """Create interactive link analysis."""
        if not PLOTLY_AVAILABLE:
            logger.warning("Plotly is not available for interactive visualization")
            return None
        
        # Convert to DataFrame
        df = self.convert_to_dataframe(data)
        
        # Find link columns
        link_cols = [c for c in df.columns if any(substr in c.lower() for substr in ['link', 'href', 'url'])]
        
        if not link_cols:
            logger.error("No link data found")
            return None
        
        # Choose the first link column for now
        link_col = link_cols[0]
        
        # Extract domain information
        if isinstance(df[link_col].iloc[0], list):
            # Handle case where links are in a list
            all_domains = []
            domain_pairs = []
            
            # Find URL column for source page
            url_col = next((c for c in df.columns if c != link_col and 'url' in c.lower()), None)
            
            if url_col:
                # Extract source domains and links
                for _, row in df.iterrows():
                    source_url = row[url_col]
                    source_domain = self._extract_domain(source_url)
                    
                    links = row[link_col]
                    if not isinstance(links, list):
                        continue
                        
                    for link in links:
                        if isinstance(link, dict) and 'href' in link:
                            target_url = link['href']
                        elif isinstance(link, str):
                            target_url = link
                        else:
                            continue
                            
                        target_domain = self._extract_domain(target_url)
                        
                        all_domains.extend([source_domain, target_domain])
                        domain_pairs.append((source_domain, target_domain))
            else:
                logger.error("No source URL column found")
                return None
        else:
            # Handle simple URLs in a column
            all_domains = df[link_col].apply(self._extract_domain).tolist()
            domain_pairs = []
        
        # Count domains
        domain_counts = Counter(all_domains)
        top_domains = dict(domain_counts.most_common(20))
        
        # Create bar chart of top domains
        fig = go.Figure(data=[
            go.Bar(
                x=list(top_domains.keys()),
                y=list(top_domains.values()),
                marker_color='lightsalmon'
            )
        ])
        
        fig.update_layout(
            title="Top Domains in Links",
            xaxis_title="Domain",
            yaxis_title="Count",
            xaxis_tickangle=-45
        )
        
        # Save if requested
        if save_path:
            full_path = os.path.join(self.output_dir, save_path)
            fig.write_html(full_path)
            logger.info(f"Link analysis saved to {full_path}")
        
        return fig
    
    def _create_static_link_analysis(self, data: Dict[str, Any], save_path: Optional[str] = None) -> Optional[plt.Figure]:
        """Create static link analysis."""
        # Convert to DataFrame
        df = self.convert_to_dataframe(data)
        
        # Find link columns
        link_cols = [c for c in df.columns if any(substr in c.lower() for substr in ['link', 'href', 'url'])]
        
        if not link_cols:
            logger.error("No link data found")
            return None