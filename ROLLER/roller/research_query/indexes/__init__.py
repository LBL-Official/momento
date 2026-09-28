"""Versioned observation indexes. Facts, not answers. Not FIRST80."""

from roller.research_query.indexes.manifest import INDEX_VERSION
from roller.research_query.indexes.reader import IndexUnavailable, open_index

__all__ = ["INDEX_VERSION", "IndexUnavailable", "open_index"]
