import json
import uuid
import inspect
from dataclasses import asdict
from datetime import datetime, date
from enum import Enum
from pathlib import Path
from typing import Dict, Generic, List, Optional, Type, TypeVar, get_type_hints

from .exceptions import JsonDBException

T = TypeVar("T")


class JsonSerializer:
    """Helper class to serialize/deserialize special types to/from JSON."""

    @staticmethod
    def default(obj):
        """Convert objects to JSON-serializable types."""
        if isinstance(obj, uuid.UUID):
            return str(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Enum):
            return obj.value
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    @staticmethod
    def object_hook_with_types(obj_dict, type_hints):
        """
        Process JSON objects during deserialization using type hints.

        Args:
            obj_dict: Dictionary to process
            type_hints: Dictionary mapping field names to their type annotations
        """
        for key, value in obj_dict.items():
            if key in type_hints:
                field_type = type_hints[key]

                # Handle UUID fields
                if field_type == uuid.UUID and isinstance(value, str):
                    try:
                        obj_dict[key] = uuid.UUID(value)
                    except ValueError:
                        pass

                # Handle date fields
                elif field_type == date and isinstance(value, str):
                    try:
                        obj_dict[key] = datetime.fromisoformat(value).date()
                    except ValueError:
                        pass

                # Handle datetime fields
                elif field_type == datetime and isinstance(value, str):
                    try:
                        obj_dict[key] = datetime.fromisoformat(value)
                    except ValueError:
                        pass

                # Handle enum fields
                elif (
                    inspect.isclass(field_type)
                    and issubclass(field_type, Enum)
                    and isinstance(value, (str, int))
                ):
                    try:
                        obj_dict[key] = field_type(value)
                    except (ValueError, KeyError):
                        pass

        return obj_dict


class JsonDB(Generic[T]):
    """A simple JSON file-based database for dataclasses."""

    def __init__(
        self, data_class: Type[T], file_path: Path, primary_key: Optional[str] = None
    ):
        """
        Initialize the database with a dataclass type and file path.

        Args:
            data_class: The dataclass type this database will store
            file_path: Path to the JSON file
            primary_key: The field name to use as primary key (optional)
        """
        self.data_class = data_class
        self.file_path = file_path
        self.primary_key = primary_key
        self.data: List[T] = []

        # Extract type hints from the dataclass
        self.type_hints = get_type_hints(data_class)

        # Validate primary key exists in dataclass if specified
        if primary_key is not None and primary_key not in self.type_hints:
            raise JsonDBException(
                f"Primary key '{primary_key}' not found in {data_class.__name__} fields"
            )

        self._load()

    def _load(self) -> None:
        """Load data from the JSON file."""
        if not self.file_path.exists():
            # Create directory if it doesn't exist
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            # Create empty file
            self._save([])
            return

        try:
            with open(self.file_path, "r") as f:
                # Custom object hook that closes over the type hints
                def object_hook(obj_dict):
                    return JsonSerializer.object_hook_with_types(
                        obj_dict, self.type_hints
                    )

                raw_data = json.load(f, object_hook=object_hook)

            self.data = [self._dict_to_dataclass(item) for item in raw_data]
        except json.JSONDecodeError as e:
            raise JsonDBException(f"Error parsing JSON file: {e}")

    def _save(self, items: List[T]) -> None:
        """Save data to the JSON file."""
        try:
            with open(self.file_path, "w") as f:
                json_data = [asdict(item) for item in items]
                json.dump(json_data, f, indent=2, default=JsonSerializer.default)
        except (TypeError, OverflowError) as e:
            raise JsonDBException(f"Error serializing to JSON: {e}")

    def _dict_to_dataclass(self, data_dict: Dict) -> T:
        """Convert a dictionary to the specified dataclass."""
        return self.data_class(**data_dict)

    def save(self) -> None:
        """Save current data to the file."""
        self._save(self.data)

    def all(self) -> List[T]:
        """Get all items."""
        return self.data.copy()

    def get(self, key_value) -> Optional[T]:
        """Get item by primary key value."""
        if self.primary_key is None:
            raise JsonDBException("Cannot use get() without a primary key configured")

        for item in self.data:
            if (
                hasattr(item, self.primary_key)
                and getattr(item, self.primary_key) == key_value
            ):
                return item
        return None

    def find(self, **kwargs) -> List[T]:
        """Find items matching the given criteria."""
        results = []
        for item in self.data:
            match = True
            for key, value in kwargs.items():
                if not hasattr(item, key) or getattr(item, key) != value:
                    match = False
                    break
            if match:
                results.append(item)
        return results

    def add(self, item: T) -> T:
        """
        Add an item to the database.

        Args:
            item: The item to add, must be of the correct type

        Returns:
            The added item

        Raises:
            JsonDBException: If the item is not of the expected type or primary key already exists
        """
        if not isinstance(item, self.data_class):
            raise JsonDBException(
                f"Item must be of type {self.data_class.__name__}, got {type(item).__name__}"
            )

        # Only check primary key constraints if primary key is configured
        if self.primary_key is not None:
            # Check if item has primary key
            if not hasattr(item, self.primary_key):
                raise JsonDBException(
                    f"Item must have a '{self.primary_key}' attribute"
                )

            # Check for primary key uniqueness
            key_value = getattr(item, self.primary_key)
            if self.get(key_value) is not None:
                raise JsonDBException(
                    f"Item with {self.primary_key}='{key_value}' already exists"
                )

        self.data.append(item)
        self.save()
        return item

    def update(self, item: T) -> T:
        """
        Update an existing item by its current primary key value.

        Args:
            item: The updated item, must be of the correct type and have a primary key

        Returns:
            The updated item

        Raises:
            JsonDBException: If the item is not of the expected type, has no primary key, or the key doesn't exist
        """
        if self.primary_key is None:
            raise JsonDBException(
                "Cannot use update() without a primary key configured"
            )

        if not isinstance(item, self.data_class):
            raise JsonDBException(
                f"Item must be of type {self.data_class.__name__}, got {type(item).__name__}"
            )

        if not hasattr(item, self.primary_key):
            raise JsonDBException(f"Item must have a '{self.primary_key}' attribute")

        key_value = getattr(item, self.primary_key)
        for i, existing_item in enumerate(self.data):
            if (
                hasattr(existing_item, self.primary_key)
                and getattr(existing_item, self.primary_key) == key_value
            ):
                self.data[i] = item
                self.save()
                return item

        raise JsonDBException(f"Item with {self.primary_key}='{key_value}' not found")

    def remove(self, key_value) -> bool:
        """Remove an item by primary key value."""
        if self.primary_key is None:
            raise JsonDBException(
                "Cannot use remove() without a primary key configured"
            )

        for i, item in enumerate(self.data):
            if (
                hasattr(item, self.primary_key)
                and getattr(item, self.primary_key) == key_value
            ):
                self.data.pop(i)
                self.save()
                return True
        return False
