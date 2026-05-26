"""Knowledge base tools for mdpilot.

Provides on-demand loading of AMBER documentation.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from mdpilot.tools.decorator import tool
from mdpilot.knowledge import KnowledgeIndex, KnowledgeLoader

logger = logging.getLogger(__name__)

# Global knowledge system (singleton)
_knowledge_index: KnowledgeIndex | None = None
_knowledge_loader: KnowledgeLoader | None = None


def _get_knowledge_system() -> tuple[KnowledgeIndex, KnowledgeLoader]:
    """Get or initialize the knowledge system.

    Returns:
        Tuple of (KnowledgeIndex, KnowledgeLoader)
    """
    global _knowledge_index, _knowledge_loader

    if _knowledge_index is None:
        # Find knowledge directory
        # Path: src/mdpilot/tools/builtin/knowledge.py -> project_root/knowledge
        # Go up 5 levels: builtin -> tools -> mdpilot -> src -> project_root
        project_root = Path(__file__).parent.parent.parent.parent.parent
        knowledge_dir = project_root / "knowledge"

        if not knowledge_dir.exists():
            raise FileNotFoundError(f"Knowledge directory not found: {knowledge_dir}")

        _knowledge_index = KnowledgeIndex(knowledge_dir)
        _knowledge_loader = KnowledgeLoader(_knowledge_index)
        logger.info(f"Knowledge system initialized from {knowledge_dir}")

    return _knowledge_index, _knowledge_loader


@tool(
    name="read_knowledge",
    description=(
        "Load detailed documentation from the AMBER knowledge base. "
        "Use this to get tool usage, concepts, workflows, and best practices. "
        "Check the knowledge base index in the system prompt for available document IDs."
    ),
    category="knowledge",
)
def read_knowledge(
    doc_ids: List[str],
    reason: str = "",
    load_related: bool = False
) -> str:
    """Load knowledge base documents.

    Args:
        doc_ids: List of document IDs to load (e.g., ['tool-pdb4amber', 'workflow-standard-protein']).
        reason: Brief explanation of why you need these documents (for logging).
        load_related: Whether to automatically load related documents. Default False.

    Returns:
        Loaded document contents in markdown format.
    """
    try:
        index, loader = _get_knowledge_system()

        # Normalize doc_ids: accept both list and comma-separated string
        if isinstance(doc_ids, str):
            import json as _json
            try:
                doc_ids = _json.loads(doc_ids)
            except _json.JSONDecodeError:
                doc_ids = [s.strip().strip('"').strip("'") for s in doc_ids.split(",") if s.strip()]

        # Log the request
        logger.info(f"[Knowledge] Loading {len(doc_ids)} docs: {reason}")
        print(f"📚 Loading knowledge: {', '.join(doc_ids)}")
        if reason:
            print(f"   Reason: {reason}")

        # Load documents
        docs = loader.load(doc_ids, load_related=load_related)

        if not docs:
            return f"Error: No documents found for IDs: {doc_ids}"

        # Format output
        output_parts = []
        for doc_id, content in docs.items():
            doc_info = index.get_doc_info(doc_id)
            title = doc_info["title"] if doc_info else doc_id

            output_parts.append(f"# Document: {doc_id}")
            output_parts.append(f"# Title: {title}")
            output_parts.append("")
            output_parts.append(content)
            output_parts.append("")
            output_parts.append("=" * 80)
            output_parts.append("")

        result = "\n".join(output_parts)

        # Add statistics
        stats = f"\n✓ Loaded {len(docs)} document(s), {len(result):,} characters total.\n"

        return result + stats

    except Exception as e:
        logger.error(f"Error loading knowledge: {e}")
        return f"Error loading knowledge: {e}"


@tool(
    name="search_knowledge",
    description=(
        "Search the AMBER knowledge base for relevant documents. "
        "Use this when you're not sure which documents you need. "
        "Returns document IDs that you can then load with read_knowledge."
    ),
    category="knowledge",
)
def search_knowledge(query: str, top_k: int = 5) -> str:
    """Search for relevant knowledge base documents.

    Args:
        query: Search query (e.g., 'ligand parameterization', 'minimize protein', 'rmsd analysis').
        top_k: Number of results to return. Default 5.

    Returns:
        List of matching documents with IDs, titles, and keywords.
    """
    try:
        index, _ = _get_knowledge_system()

        # Search
        results = index.search(query, top_k=top_k)

        if not results:
            return f"No documents found matching '{query}'.\n\nTry broader terms or check the knowledge base index."

        # Format results
        output = [f"Found {len(results)} document(s) matching '{query}':\n"]

        for i, doc in enumerate(results, 1):
            doc_id = doc.get("id", doc.get("title", "unknown"))
            output.append(f"{i}. **{doc_id}**: {doc['title']}")
            keywords = ", ".join(doc.get("keywords", doc.get("tags", []))[:5])
            output.append(f"   Keywords: {keywords}")

            if "use_cases" in doc and doc["use_cases"]:
                use_cases = ", ".join(doc["use_cases"][:2])
                output.append(f"   Use cases: {use_cases}")

            output.append("")

        output.append("💡 Use `read_knowledge` with the document ID to load full content.")

        return "\n".join(output)

    except Exception as e:
        logger.error(f"Error searching knowledge: {e}")
        return f"Error searching knowledge: {e}"


@tool(
    name="list_knowledge",
    description=(
        "List all available documents in the knowledge base by category. "
        "Use this to browse what's available."
    ),
    category="knowledge",
)
def list_knowledge(category: str | None = None) -> str:
    """List available knowledge base documents.

    Args:
        category: Optional category filter ('tools', 'concepts', 'workflows'). If None, lists all.

    Returns:
        Formatted list of available documents.
    """
    try:
        index, _ = _get_knowledge_system()

        output = ["# Available Knowledge Base Documents\n"]

        categories = index.index["categories"]

        if category:
            # List specific category
            if category not in categories:
                return f"Error: Unknown category '{category}'. Available: tools, concepts, workflows"

            cat_data = categories[category]
            output.append(f"## {category.title()} ({len(cat_data['documents'])} documents)\n")

            for doc in cat_data["documents"]:
                doc_id = index._get_doc_id(doc)
                output.append(f"- **{doc_id}**: {doc['title']}")
                keywords = ", ".join(doc.get("keywords", doc.get("tags", []))[:3])
                output.append(f"  Keywords: {keywords}")
                output.append("")
        else:
            # List all categories
            for cat_name, cat_data in categories.items():
                output.append(f"## {cat_name.title()} ({len(cat_data['documents'])} documents)\n")

                for doc in cat_data["documents"]:
                    doc_id = index._get_doc_id(doc)
                    output.append(f"- **{doc_id}**: {doc['title']}")

                output.append("")

        output.append("💡 Use `search_knowledge` to find specific topics.")
        output.append("💡 Use `read_knowledge` to load full documentation.")

        return "\n".join(output)

    except Exception as e:
        logger.error(f"Error listing knowledge: {e}")
        return f"Error listing knowledge: {e}"


def get_knowledge_index_summary() -> str:
    """Get lightweight knowledge index summary for system prompt.

    Returns:
        Formatted index summary
    """
    try:
        index, _ = _get_knowledge_system()
        return index.get_index_summary()
    except Exception as e:
        logger.error(f"Error getting knowledge summary: {e}")
        return "# Knowledge Base (unavailable)\n"
