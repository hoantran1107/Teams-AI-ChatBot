from enum import Enum

# List of special separators that might appear in text
special_separators = [
    "\xa0",  # Non-breaking space
    "\u200b",  # Zero-width space
    "\uff0c",  # Fullwidth comma
    "\u3001",  # Ideographic comma
    "\uff0e",  # Fullwidth full stop
    "\u3002",  # Ideographic full stop
]

file_separator = "*"  # Used as a file name separator


class VectorStoreDefaultCollection(Enum):
    """Enum for different vector store collections."""

    KB = "Company Knowledge Base"

    @staticmethod
    def get_sources():
        return [v.value for v in VectorStoreDefaultCollection]
