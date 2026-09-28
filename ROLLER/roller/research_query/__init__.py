"""Generic empirical research-query engine.

Independent of research_spec and FIRST80 frozen bindings.
QUESTION PRESERVATION > TEMPLATE CONVENIENCE.
CANDLE PATH ≠ FILL. GENERIC ≠ FIRST80.
"""

from roller.research_query.compiler import compile_question
from roller.research_query.execute import execute_question
from roller.research_query.models import ResearchQuestion, ResearchStatus

__all__ = [
    "ResearchQuestion",
    "ResearchStatus",
    "compile_question",
    "execute_question",
]
