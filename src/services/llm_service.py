"""
LLM service wrapper
Provides unified interface for fast and premium models
"""

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from typing import Any, Dict, Type
from pydantic import BaseModel

from src.config import settings
from src.utils.logging import logger


class LLMService:
    """
    LLM client wrapper with tiered model strategy
    """
    
    def __init__(self):
        """Initialize fast and premium models"""
        self.fast_model = ChatOpenAI(
            model=settings.fast_model,
            temperature=0,
            api_key=settings.openai_api_key
        )
        
        self.premium_model = ChatOpenAI(
            model=settings.premium_model,
            temperature=0,
            api_key=settings.openai_api_key
        )
    
    def invoke_fast(
        self,
        prompt: str,
        schema: Type[BaseModel]
    ) -> BaseModel:
        """
        Invoke fast model with structured output
        
        Args:
            prompt: Input prompt
            schema: Pydantic model for structured output
            
        Returns:
            Parsed response matching schema
        """
        logger.debug(
            "llm_invoke",
            model=settings.fast_model,
            schema=schema.__name__
        )
        
        structured_llm = self.fast_model.with_structured_output(schema)
        return structured_llm.invoke(prompt)
    
    def invoke_premium(
        self,
        prompt: str,
        schema: Type[BaseModel]
    ) -> BaseModel:
        """
        Invoke premium model with structured output
        
        Args:
            prompt: Input prompt
            schema: Pydantic model for structured output
            
        Returns:
            Parsed response matching schema
        """
        logger.debug(
            "llm_invoke",
            model=settings.premium_model,
            schema=schema.__name__
        )
        
        structured_llm = self.premium_model.with_structured_output(schema)
        return structured_llm.invoke(prompt)


# Global service instance
llm_service = LLMService()
