"""Simple JSON Database - A lightweight JSON-based database for Python applications."""

from .database import JsonDB, JsonSerializer
from .exceptions import JsonDBException

__version__ = "0.1.0"
__all__ = [
    "JsonDB",
    "JsonSerializer",
    "JsonDBException",
]


def main() -> None:
    """Entry point for the CLI."""
    print(
        "Simple JSON Database - A lightweight JSON-based database for Python applications"
    )
    print(f"Version: {__version__}")
    print(
        "Visit https://github.com/frangiz/simple-json-db for documentation and examples"
    )
