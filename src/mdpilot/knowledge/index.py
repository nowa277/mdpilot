"""
Knowledge base index management.

Provides lightweight indexing and search capabilities for the knowledge base.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional


def _get_keywords(doc: Dict) -> list[str]:
    """Extract keywords from a document, handling both 'keywords' and 'tags' fields."""
    return doc.get("keywords", doc.get("tags", []))


class KnowledgeIndex:
    """Knowledge base index manager."""

    def __init__(self, knowledge_dir: Path):
        """Initialize knowledge index.

        Args:
            knowledge_dir: Path to knowledge base directory
        """
        self.knowledge_dir = Path(knowledge_dir)
        self.index = self._load_index()

    def _load_index(self) -> Dict:
        """Load index file."""
        index_file = self.knowledge_dir / "index.json"
        if not index_file.exists():
            raise FileNotFoundError(f"Knowledge index not found: {index_file}")

        with open(index_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _get_doc_id(self, doc: Dict) -> str:
        """Get document ID, deriving from path if 'id' field is missing."""
        if "id" in doc:
            return doc["id"]
        # Derive ID from path:
        #   "1-tools/pdb4amber.md" -> "pdb4amber"
        #   "3-workflows/standard-protein/README.md" -> "standard-protein"
        path = doc.get("path", "")
        if path:
            parts = Path(path)
            # If filename is generic (README, index), use parent dir name
            if parts.stem.lower() in ("readme", "index"):
                return parts.parent.name
            return parts.stem
        return doc.get("title", "unknown")

    def get_index_summary(self) -> str:
        """Generate lightweight index summary for system prompt.

        Returns:
            Formatted index summary (~2KB)
        """
        summary = ["# Available Knowledge Base\n"]

        # Tools
        tools = self.index["categories"]["tools"]["documents"]
        summary.append(f"## Tools Documentation ({len(tools)} documents)")
        for tool in tools:
            kw = _get_keywords(tool)
            keywords = ", ".join(kw[:3]) if kw else ""
            doc_id = self._get_doc_id(tool)
            summary.append(f"- `{doc_id}`: {tool['title']}")
            if keywords:
                summary.append(f"  Keywords: {keywords}")

        # Concepts
        concepts = self.index["categories"]["concepts"]["documents"]
        summary.append(f"\n## Concepts Documentation ({len(concepts)} documents)")
        for concept in concepts:
            kw = _get_keywords(concept)
            keywords = ", ".join(kw[:3]) if kw else ""
            doc_id = self._get_doc_id(concept)
            summary.append(f"- `{doc_id}`: {concept['title']}")
            if keywords:
                summary.append(f"  Keywords: {keywords}")

        # Workflows
        workflows = self.index["categories"]["workflows"]["documents"]
        summary.append(f"\n## Workflows Documentation ({len(workflows)} documents)")
        for wf in workflows:
            doc_id = self._get_doc_id(wf)
            summary.append(f"- `{doc_id}`: {wf['title']}")

        summary.append("\n**Usage**: Use `read_knowledge` tool to load detailed documentation.")
        summary.append("Use `search_knowledge` tool to find relevant documents.")

        return "\n".join(summary)

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """Search for relevant documents.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of matching documents with scores
        """
        query_lower = query.lower()
        results = []

        for category in self.index["categories"].values():
            for doc in category["documents"]:
                score = 0

                # Title match (highest weight)
                if query_lower in doc["title"].lower():
                    score += 10

                # Keyword/tag match
                for keyword in _get_keywords(doc):
                    if query_lower in keyword.lower():
                        score += 5

                # Use case match
                for use_case in doc.get("use_cases", []):
                    if query_lower in use_case.lower():
                        score += 3

                # ID match
                doc_id = self._get_doc_id(doc)
                if query_lower in doc_id.lower():
                    score += 8

                if score > 0:
                    doc_id = self._get_doc_id(doc)
                    result = dict(doc, id=doc_id)
                    results.append({"doc": result, "score": score})

        # Sort by score
        results.sort(key=lambda x: x["score"], reverse=True)
        return [r["doc"] for r in results[:top_k]]

    def get_doc_path(self, doc_id_search: str) -> Optional[Path]:
        """Get file path for a document ID.

        Args:
            doc_id_search: Document identifier

        Returns:
            Path to document file, or None if not found
        """
        for category in self.index["categories"].values():
            for doc in category["documents"]:
                if self._get_doc_id(doc) == doc_id_search:
                    return self.knowledge_dir / doc["path"]
        return None

    def get_doc_info(self, doc_id_search: str) -> Optional[Dict]:
        """Get document metadata.

        Args:
            doc_id_search: Document identifier

        Returns:
            Document metadata dict, or None if not found
        """
        for category in self.index["categories"].values():
            for doc in category["documents"]:
                if self._get_doc_id(doc) == doc_id_search:
                    return doc
        return None

    def get_related_docs(self, doc_id_search: str) -> List[str]:
        """Get related document IDs.

        Args:
            doc_id: Document identifier

        Returns:
            List of related document IDs
        """
        doc_info = self.get_doc_info(doc_id_search)
        if doc_info:
            return doc_info.get("related", [])
        return []

    def list_all_docs(self) -> List[Dict]:
        """List all documents in the knowledge base.

        Returns:
            List of all document metadata
        """
        all_docs = []
        for category in self.index["categories"].values():
            all_docs.extend(category["documents"])
        return all_docs
