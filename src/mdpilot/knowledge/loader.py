"""
Knowledge document loader.

Handles loading and caching of knowledge base documents.
"""

from pathlib import Path
from typing import Dict, List, Optional, Set
from .index import KnowledgeIndex


class KnowledgeLoader:
    """Knowledge document loader with caching."""

    def __init__(self, index: KnowledgeIndex, max_cache_size: int = 50):
        """Initialize knowledge loader.

        Args:
            index: Knowledge index instance
            max_cache_size: Maximum number of documents to cache
        """
        self.index = index
        self.max_cache_size = max_cache_size
        self.cache: Dict[str, str] = {}
        self.access_count: Dict[str, int] = {}
        self.load_stats: Dict[str, int] = {}
        self.total_chars_loaded = 0

    def load(
        self,
        doc_ids: List[str],
        load_related: bool = False
    ) -> Dict[str, str]:
        """Load documents by ID.

        Args:
            doc_ids: List of document IDs to load
            load_related: Whether to automatically load related documents

        Returns:
            Dict mapping doc_id to document content
        """
        # Expand doc list if loading related
        all_doc_ids: Set[str] = set(doc_ids)
        if load_related:
            for doc_id in doc_ids:
                related = self.index.get_related_docs(doc_id)
                all_doc_ids.update(related)

        # Load documents
        results = {}
        for doc_id in all_doc_ids:
            content = self._load_single(doc_id)
            if content:
                results[doc_id] = content

        return results

    def _load_single(self, doc_id: str) -> Optional[str]:
        """Load a single document.

        Args:
            doc_id: Document identifier

        Returns:
            Document content, or None if not found
        """
        # Check cache first
        if doc_id in self.cache:
            self.access_count[doc_id] += 1
            return self.cache[doc_id]

        # Load from disk
        doc_path = self.index.get_doc_path(doc_id)
        if doc_path is None:
            return None

        if not doc_path.exists():
            return None

        try:
            with open(doc_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Update cache
            self._cache_put(doc_id, content)

            # Update stats
            self.load_stats[doc_id] = self.load_stats.get(doc_id, 0) + 1
            self.total_chars_loaded += len(content)

            return content

        except Exception as e:
            print(f"[Knowledge] Error loading {doc_id}: {e}")
            return None

    def _cache_put(self, doc_id: str, content: str):
        """Add document to cache with LRU eviction.

        Args:
            doc_id: Document identifier
            content: Document content
        """
        # Evict if cache is full
        if len(self.cache) >= self.max_cache_size:
            # Find least recently used
            if self.access_count:
                least_used = min(self.access_count, key=self.access_count.get)
                del self.cache[least_used]
                del self.access_count[least_used]

        # Add to cache
        self.cache[doc_id] = content
        self.access_count[doc_id] = 1

    def get_stats(self) -> Dict:
        """Get loading statistics.

        Returns:
            Statistics dictionary
        """
        top_docs = sorted(
            self.load_stats.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]

        return {
            "total_loads": sum(self.load_stats.values()),
            "unique_docs": len(self.load_stats),
            "total_chars": self.total_chars_loaded,
            "cache_size": len(self.cache),
            "top_docs": top_docs
        }

    def clear_cache(self):
        """Clear the document cache."""
        self.cache.clear()
        self.access_count.clear()
