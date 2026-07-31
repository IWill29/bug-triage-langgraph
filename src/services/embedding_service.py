"""
Embedding service for duplicate detection
Generates embeddings for semantic similarity search
"""

from langchain_openai import OpenAIEmbeddings
from typing import List
import numpy as np

from src.config import settings
from src.utils.logging import logger

try:
    from langsmith import traceable
except ImportError:  # pragma: no cover
    def traceable(**kwargs):  # type: ignore[misc]
        def decorator(func):
            return func
        return decorator


class EmbeddingService:
    """
    Embedding generation for duplicate detection
    Uses OpenAI text-embedding-3-large (1536 dimensions via truncation)
    """
    
    def __init__(self):
        """Initialize OpenAI embeddings"""
        self.embeddings = OpenAIEmbeddings(
            model=settings.embedding_model,
            api_key=settings.openai_api_key,
            dimensions=settings.embedding_dimensions,
        )
    
    @traceable(name="embed_for_duplicate_check")
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding vector for text
        
        Args:
            text: Input text to embed
            
        Returns:
            1536-dimensional embedding vector
        """
        logger.debug(
            "generate_embedding",
            text_length=len(text),
            model=settings.embedding_model
        )
        
        embedding = self.embeddings.embed_query(text)
        return embedding
    
    def cosine_similarity(
        self,
        embedding1: List[float],
        embedding2: List[float]
    ) -> float:
        """
        Calculate cosine similarity between two embeddings
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Similarity score 0.0-1.0
        """
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
        similarity = np.dot(vec1, vec2) / (
            np.linalg.norm(vec1) * np.linalg.norm(vec2)
        )
        
        return float(similarity)


# Global service instance
embedding_service = EmbeddingService()
