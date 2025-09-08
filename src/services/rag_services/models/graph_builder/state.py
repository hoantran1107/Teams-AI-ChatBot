import pandas as pd
from langgraph.graph import MessagesState


class GraphState(MessagesState):
    """State for the graph builder."""

    question: str
    analysis_results: str
    gen_queries: list[str]
    documents: list[dict]
    analyze_table: bool
    language: str
    tables: list[pd.DataFrame]
    chat_state: dict
    history: list
    instructions: list[dict]
    debug: dict
    classification_message: str
    node_message: dict
    using_memory: bool
