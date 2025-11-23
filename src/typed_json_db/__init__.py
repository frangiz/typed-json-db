"""Simple JSON Database - A lightweight JSON-based database for Python applications."""

from .database import JsonDB, IndexedJsonDB, JsonSerializer
from .exceptions import JsonDBException
from .models import Timestamped

__version__ = "0.3.0"
__all__ = [
    "JsonDB",
    "IndexedJsonDB",
    "JsonSerializer",
    "JsonDBException",
    "Timestamped",
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
