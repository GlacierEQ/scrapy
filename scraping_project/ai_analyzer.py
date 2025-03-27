"""
AI-powered content analysis module for enhanced data extraction and understanding.

This module uses state-of-the-art NLP models to analyze web content,
extract structured information, and provide insights.
"""

import logging
import os
import json
import time
from typing import Dict, List, Any, Optional, Union, Tuple
import numpy as np
from datetime import datetime

# Check if transformers is available, otherwise provide guidance
try:
    import torch
    from transformers import (
        AutoTokenizer, 
        AutoModelForSequenceClassification, 
        AutoModelForQuestionAnswering,
        AutoModelForTokenClassification,
        pipeline
    )
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

from .memory_manager import get_memory_manager

logger = logging.getLogger(__name__)
memory_manager = get_memory_manager()

class AIContentAnalyzer:
    """
    Analyzes web content using state-of-the-art AI models.
    
    Features:
    - Content classification (topics, categories, sentiment)
    - Named entity recognition (people, organizations, locations)
    - Key information extraction based on templates
    - Summary generation
    - Question answering on content
    """
    
    def __init__(self, use_gpu: bool = False, cache_dir: Optional[str] = None):
        """
        Initialize the AI content analyzer.
        
        Args:
            use_gpu: Whether to use GPU acceleration if available
            cache_dir: Directory to cache downloaded models
        """
        self.use_gpu = use_gpu and torch.cuda.is_available()
        self.device = torch.device('cuda' if self.use_gpu else 'cpu')
        self.cache_dir = cache_dir
        
        # Track loaded models to avoid reloading
        self.loaded_models = {}
        
        # Check if transformers is available
        if not TRANSFORMERS_AVAILABLE:
            logger.warning(
                "Transformers library not installed. AI analysis features will be limited. "
                "Install with: pip install transformers[torch]"
            )
        
        logger.info(f"AI Content Analyzer initialized (Using GPU: {self.use_gpu})")
    
    def analyze_content(self, text: str, analysis_types: List[str] = None) -> Dict[str, Any]:
        """
        Perform comprehensive AI analysis on content.
        
        Args:
            text: Text content to analyze
            analysis_types: List of analysis types to perform 
                           (e.g., ['classification', 'sentiment', 'entities'])
                           If None, performs all available analyses
                           
        Returns:
            Dictionary with analysis results
        """
        if not TRANSFORMERS_AVAILABLE:
            return {"error": "Transformers library not installed"}
        
        # Default to all analysis types if not specified
        if analysis_types is None:
            analysis_types = ['classification', 'sentiment', 'entities', 'summary']
        
        results = {}
        
        # Use memory_manager to track memory usage during intensive operations
        with memory_manager.memory_safe_operation("ai_content_analysis"):
            # Process text in chunks if it's too long
            text_chunks = self._chunk_text(text)
            
            # Perform requested analyses
            if 'classification' in analysis_types:
                results['classification'] = self.classify_content(text_chunks[0] if text_chunks else text)
                
            if 'sentiment' in analysis_types:
                results['sentiment'] = self.analyze_sentiment(text)
                
            if 'entities' in analysis_types:
                results['entities'] = self.extract_entities(text)
                
            if 'summary' in analysis_types:
                results['summary'] = self.generate_summary(text)
                
            if 'keywords' in analysis_types:
                results['keywords'] = self.extract_keywords(text)
        
        return results
    
    def classify_content(self, text: str) -> Dict[str, float]:
        """
        Classify content into categories.
        
        Args:
            text: Text to classify
            
        Returns:
            Dictionary mapping categories to confidence scores
        """
        # Load or retrieve the classification model
        classifier = self._get_pipeline(
            'zero-shot-classification',
            model="facebook/bart-large-mnli"
        )
        
        # Define potential categories
        categories = [
            "technology", "business", "politics", "entertainment", 
            "sports", "science", "health", "education", "travel",
            "finance", "food", "fashion", "law", "environment",
            "art", "real estate", "gaming"
        ]
        
        # Truncate text if too long
        max_length = 1024
        if len(text) > max_length:
            text = text[:max_length]
        
        # Perform classification
        try:
            result = classifier(text, categories)
            return dict(zip(result['labels'], result['scores']))
        except Exception as e:
            logger.error(f"Error during content classification: {str(e)}")
            return {"error": str(e)}
    
    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """
        Analyze sentiment of text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Dictionary with sentiment analysis results
        """
        # Load or retrieve the sentiment analysis model
        sentiment_analyzer = self._get_pipeline(
            'sentiment-analysis',
            model="distilbert-base-uncased-finetuned-sst-2-english"
        )
        
        # Process text in chunks for long content
        chunks = self._chunk_text(text, max_length=512, overlap=50)
        
        results = []
        for chunk in chunks[:10]:  # Limit to first 10 chunks to avoid excessive processing
            try:
                result = sentiment_analyzer(chunk)
                results.extend(result)
            except Exception as e:
                logger.error(f"Error during sentiment analysis: {str(e)}")
        
        # Aggregate results
        if not results:
            return {"error": "Failed to analyze sentiment"}
        
        # Count sentiment occurrences
        sentiment_counts = {}
        for result in results:
            label = result['label']
            score = result['score']
            
            if label not in sentiment_counts:
                sentiment_counts[label] = {"count": 0, "total_score": 0.0}
            
            sentiment_counts[label]["count"] += 1
            sentiment_counts[label]["total_score"] += score
        
        # Calculate averages
        sentiment_summary = {}
        for label, data in sentiment_counts.items():
            avg_score = data["total_score"] / data["count"]
            sentiment_summary[label] = {
                "frequency": data["count"] / len(results),
                "average_score": avg_score
            }
        
        # Determine dominant sentiment
        dominant = max(sentiment_summary.items(), key=lambda x: x[1]["frequency"])
        
        return {
            "dominant_sentiment": dominant[0],
            "dominant_score": dominant[1]["average_score"],
            "sentiment_distribution": sentiment_summary,
            "analyzed_segments": len(results)
        }
    
    def extract_entities(self, text: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract named entities from text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Dictionary mapping entity types to lists of extracted entities
        """
        # Load or retrieve the NER model
        ner = self._get_pipeline(
            'ner',
            model="dbmdz/bert-large-cased-finetuned-conll03-english"
        )
        
        # Process text in chunks for long content
        chunks = self._chunk_text(text, max_length=512, overlap=100)
        
        all_entities = []
        for chunk in chunks[:5]:  # Limit to first 5 chunks
            try:
                chunk_entities = ner(chunk)
                if chunk_entities:
                    all_entities.extend(chunk_entities)
            except Exception as e:
                logger.error(f"Error during entity extraction: {str(e)}")
        
        # Group entities by type
        entity_groups = {}
        current_entity = None
        
        for entity in all_entities:
            # Handle B- (beginning) and I- (inside) tags
            if entity['entity'].startswith('B-'):
                # New entity starts
                if current_entity:
                    entity_type = current_entity['type']
                    if entity_type not in entity_groups:
                        entity_groups[entity_type] = []
                    entity_groups[entity_type].append(current_entity)
                
                # Start a new entity
                current_entity = {
                    'text': entity['word'],
                    'type': entity['entity'][2:],
                    'score': entity['score']
                }
            elif entity['entity'].startswith('I-') and current_entity:
                # Continue current entity
                current_entity['text'] += ' ' + entity['word']
                current_entity['score'] = (current_entity['score'] + entity['score']) / 2
            else:
                # Handle single word entities or reset
                if current_entity:
                    entity_type = current_entity['type']
                    if entity_type not in entity_groups:
                        entity_groups[entity_type] = []
                    entity_groups[entity_type].append(current_entity)
                    current_entity = None
        
        # Add the last entity if there is one
        if current_entity:
            entity_type = current_entity['type']
            if entity_type not in entity_groups:
                entity_groups[entity_type] = []
            entity_groups[entity_type].append(current_entity)
        
        # Clean up entity groups and remove duplicates
        for entity_type, entities in entity_groups.items():
            # Remove duplicates based on text
            seen_text = set()
            unique_entities = []
            
            for entity in entities:
                if entity['text'] not in seen_text:
                    seen_text.add(entity['text'])
                    unique_entities.append(entity)
            
            # Sort by score
            entity_groups[entity_type] = sorted(
                unique_entities, 
                key=lambda x: x['score'], 
                reverse=True
            )
        
        return entity_groups
    
    def generate_summary(self, text: str, max_length: int = 150) -> str:
        """
        Generate a concise summary of the text.
        
        Args:
            text: Text to summarize
            max_length: Maximum length of the summary
            
        Returns:
            Generated summary
        """
        # Load or retrieve the summarization model
        summarizer = self._get_pipeline(
            'summarization',
            model="facebook/bart-large-cnn"
        )
        
        # Ensure text is not too long for model
        max_input_length = 1024
        if len(text) > max_input_length:
            text = text[:max_input_length]
        
        try:
            summary = summarizer(
                text, 
                max_length=max_length, 
                min_length=30, 
                do_sample=False
            )
            
            return summary[0]['summary_text']
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            return ""
    
    def extract_keywords(self, text: str, top_n: int = 10) -> List[str]:
        """
        Extract key phrases and topics from text.
        
        Args:
            text: Text to analyze
            top_n: Number of keywords to extract
            
        Returns:
            List of extracted keywords/phrases
        """
        try:
            # We'll use a simple statistical approach combined with NER
            # This can be enhanced with topic modeling (e.g., LDA) if needed
            
            # Extract entities first as they are often important
            entities = self.extract_entities(text)
            
            # Flatten entity list
            keywords = []
            for entity_type, entity_list in entities.items():
                keywords.extend([entity['text'] for entity in entity_list[:5]])
            
            # Use transformers keyword extraction if available
            try:
                keyword_extractor = self._get_pipeline(
                    'feature-extraction',
                    model="distilbert-base-cased"
                )
                
                # Implement a statistical approach using the embeddings
                # (This is a placeholder - in a real implementation, we would 
                # do more sophisticated processing with the embeddings)
                
                # For now, just ensure we have the top entity-based keywords
                return list(set(keywords))[:top_n]
                
            except Exception as e:
                logger.warning(f"Could not use transformer for keyword extraction: {e}")
                return keywords[:top_n]
                
        except Exception as e:
            logger.error(f"Error extracting keywords: {str(e)}")
            return []
    
    def answer_question(self, context: str, question: str) -> Dict[str, Any]:
        """
        Answer a specific question based on the context text.
        
        Args:
            context: Text to search for answers
            question: Question to answer
            
        Returns:
            Dictionary with answer and confidence score
        """
        # Load or retrieve QA model
        qa_pipeline = self._get_pipeline(
            'question-answering',
            model="deepset/roberta-base-squad2"
        )
        
        try:
            # Ensure context is not too long
            max_context = 512
            if len(context) > max_context:
                # Try to find a relevant section
                result = self._find_relevant_section(context, question, max_context)
            else:
                result = qa_pipeline(question=question, context=context)
                
            return {
                "answer": result['answer'],
                "confidence": result['score'],
                "start": result['start'],
                "end": result['end']
            }
            
        except Exception as e:
            logger.error(f"Error in question answering: {str(e)}")
            return {"answer": "", "confidence": 0, "error": str(e)}
    
    def _find_relevant_section(self, context: str, question: str, max_length: int) -> Dict[str, Any]:
        """Find the most relevant section of text for a question."""
        # Split into paragraphs
        paragraphs = [p for p in context.split('\n\n') if p.strip()]
        
        if not paragraphs:
            paragraphs = [context]
        
        qa_pipeline = self._get_pipeline(
            'question-answering',
            model="deepset/roberta-base-squad2"
        )
        
        # Search each paragraph
        best_answer = None
        best_score = -1
        
        for para in paragraphs:
            if len(para) > max_length:
                para = para[:max_length]
                
            try:
                result = qa_pipeline(question=question, context=para)
                
                if result['score'] > best_score:
                    best_score = result['score']
                    best_answer = result
            except:
                continue
        
        if best_answer:
            return best_answer
        
        # If no good answer, try with the beginning of the text
        return qa_pipeline(question=question, context=context[:max_length])
    
    def _get_pipeline(self, task: str, model: str) -> Any:
        """
        Get or create a pipeline for the specified task.
        
        Args:
            task: The pipeline task
            model: Model to use for the task
            
        Returns:
            Pipeline for the task
        """
        key = f"{task}_{model}"
        
        if key in self.loaded_models:
            return self.loaded_models[key]
        
        try:
            # Create the pipeline
            nlp_pipeline = pipeline(
                task,
                model=model,
                tokenizer=model,
                device=0 if self.use_gpu else -1,
                cache_dir=self.cache_dir
            )
            
            # Store for reuse
            self.loaded_models[key] = nlp_pipeline
            return nlp_pipeline
            
        except Exception as e:
            logger.error(f"Error creating pipeline for {task} using {model}: {str(e)}")
            raise
    
    def _chunk_text(self, text: str, max_length: int = 1000, overlap: int = 200) -> List[str]:
        """Split text into overlapping chunks."""
        if len(text) <= max_length:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = min(start + max_length, len(text))
            
            # Try to find a sentence boundary for a cleaner cut
            if end < len(text):
                # Look for common sentence endings within 100 chars of the proposed end
                search_range_end = min(end + 100, len(text))
                search_text = text[end:search_range_end]
                
                # Find the first sentence boundary
                boundary_markers = ['. ', '! ', '? ', '\n\n']
                boundaries = [search_text.find(marker) for marker in boundary_markers]
                valid_boundaries = [b for b in boundaries if b != -1]
                
                if valid_boundaries:
                    # Add the closest boundary position to the end
                    end += min(valid_boundaries) + 2  # +2 for the boundary marker
            
            chunks.append(text[start:end])
            start = end - overlap  # Create overlap with previous chunk
        
        return chunks

    def cleanup(self):
        """Free up memory by clearing loaded models."""
        self.loaded_models.clear()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
