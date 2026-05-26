"""
Knowledge base management for Amber-Agent.

This module provides on-demand knowledge loading from the AMBER documentation.
"""

from .index import KnowledgeIndex
from .loader import KnowledgeLoader

__all__ = ["KnowledgeIndex", "KnowledgeLoader"]
