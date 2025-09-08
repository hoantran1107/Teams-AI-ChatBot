import re
from typing import Any


def extract_table_data(text: str) -> dict[str, str | None]:
    """Extract table data from JSON-like text.

    Args:
        text: The text containing JSON-like data with result and code fields.

    Returns:
        A dictionary with extracted xml_string and code_string.

    """
    # Extract the result value using regex
    result_match = re.search(r'"result"\s*:\s*"((?:\\.|[^"\\])*)"', text, re.DOTALL)
    result = (
        result_match.group(1).replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\") if result_match else None
    )

    # Extract the code value using regex
    code_match = re.search(r'"code"\s*:\s*"((?:\\.|[^"\\])*)"', text, re.DOTALL)
    code = code_match.group(1).replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\") if code_match else None

    return {
        "xml_string": result,
        "code_string": code,
    }


def process_citations(data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Process citations data into a standardized format.

    Args:
        data: A list of dictionaries containing citation metadata.

    Returns:
        A list of formatted citation dictionaries.

    """
    citations = [
        {
            "titles": item["metadata"]["titles"],
            "topic": item["metadata"]["topic"],
            "view_url": item["metadata"]["view_url"],
            "document_collection": item["metadata"].get("document_collection", "Unknown Collection"),
        }
        for item in data
    ]

    return citations
