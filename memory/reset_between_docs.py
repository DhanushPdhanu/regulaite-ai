"""reset_between_docs.py
Resets RAG and bridge state between documents.
Shashank's server.py calls reset_for_new_document() before each new upload.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory import rag as rag_module
from memory import bridge as bridge_module
import networkx as nx


def reset_for_new_document() -> dict:
    """Flushes all in-memory state between document analyses.
    Must be called before indexing a new document."""
    # Reset RAG instance
    bridge_module._rag_instance = None
    bridge_module._indexed_clauses = []

    # Reset citation graph
    rag_module.citation_graph.clear()
    bridge_module.citation_graph = rag_module.citation_graph

    return {
        "status": "reset",
        "message": "RAG store and citation graph cleared. Ready for new document.",
    }


if __name__ == "__main__":
    result = reset_for_new_document()
    print(result)
