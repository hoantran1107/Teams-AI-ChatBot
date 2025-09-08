"""
Environment variable loader module.
Centralizes the loading of environment variables to avoid duplication.
"""
import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Load environment variables once at module level
load_dotenv()

class EnvironmentVariables:
    """Class for accessing environment variables with type conversion and defaults"""
    
    @staticmethod
    def get_str(key: str, default: str = "") -> str:
        """Get environment variable as string with default"""
        return os.environ.get(key, default)
    
    @staticmethod
    def get_int(key: str, default: int = 0) -> int:
        """Get environment variable as integer with default"""
        value = os.environ.get(key)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            return default
    
    @staticmethod
    def get_bool(key: str, default: bool = False) -> bool:
        """Get environment variable as boolean with default"""
        value = os.environ.get(key, "").lower()
        if value in ("true", "1", "yes", "y"):
            return True
        if value in ("false", "0", "no", "n"):
            return False
        return default
    
    @staticmethod
    def get_required(key: str) -> str:
        """Get a required environment variable, raises KeyError if not found"""
        value = os.environ.get(key)
        if value is None:
            raise KeyError(f"Required environment variable '{key}' is not set")
        return value

    @staticmethod
    def get_dict(prefix: str, separator: str = "_") -> Dict[str, str]:
        """Get all environment variables with a specific prefix as a dictionary"""
        result = {}
        for key, value in os.environ.items():
            if key.startswith(prefix):
                # Remove prefix and separator
                clean_key = key[len(prefix) + len(separator):] if key.startswith(f"{prefix}{separator}") else key[len(prefix):]
                result[clean_key] = value
        return result

# Create a singleton instance for easy import
env = EnvironmentVariables()