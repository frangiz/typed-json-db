import json
import uuid
import inspect
from dataclasses import asdict, replace
from datetime import datetime, date
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Dict,
    Generic,
    Iterator,
    List,
    Optional,
    Type,
    TypeVar,
    Union,
    get_type_hints,
    get_origin,
    get_args,
)

from .exceptions import JsonDBException

T = TypeVar("T")
PK = TypeVar("PK")  # Primary Key type


class JsonSerializer:
    """Helper class to serialize/deserialize special types to/from JSON."""

    @staticmethod
    def default(obj: Any) -> Any:
        """
        Convert special Python objects to JSON-serializable types.

        This method is intended to be used as the `default` function for `json.dumps`.

        Args:
            obj (Any): The object to convert.

        Returns:
            Any: A JSON-serializable representation of the object.

        Supported types:
            - uuid.UUID: converted to string
            - datetime, date: converted to ISO 8601 string
            - Enum: converted to its value

        Raises:
            TypeError: If the object type is not supported for JSON serialization.
        """
        if isinstance(obj, uuid.UUID):
            return str(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Enum):
            return obj.value
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    @staticmethod
    def object_hook_with_types(
        obj_dict: Dict[str, Any], type_hints: Dict[str, Type[Any]], max_depth: int = 10
    ) -> Dict[str, Any]:
        """
        Process JSON objects during deserialization using type hints.

        Args:
            obj_dict: Dictionary to process
            type_hints: Dictionary mapping field names to their type annotations
            max_depth: Maximum recursion depth to prevent infinite recursion (default: 10)
        """
        # Guard against excessive recursion
        if max_depth <= 0:
            return obj_dict

        for key, value in obj_dict.items():
            if key in type_hints:
                field_type = type_hints[key]
                origin_type = get_origin(field_type)

                # Extract actual type from Optional[T] (which is Union[T, None])
                actual_type = field_type
                if origin_type is Union:
                    args = get_args(field_type)
                    if args:
                        # Get the non-None type from Optional
                        actual_type = next(
                            (arg for arg in args if arg is not type(None)), field_type
                        )
                        origin_type = get_origin(actual_type)

                # Handle List of dataclasses
                if origin_type is list and isinstance(value, list):
                    try:
                        args = get_args(field_type)
                        if (
                            args
                            and inspect.isclass(args[0])
                            and hasattr(args[0], "__dataclass_fields__")
                        ):
                            nested_type = args[0]
                            nested_type_hints = get_type_hints(nested_type)
                            # Decrement depth for recursive calls
                            obj_dict[key] = [
                                nested_type(
                                    **JsonSerializer.object_hook_with_types(
                                        item, nested_type_hints, max_depth - 1
                                    )
                                )
                                for item in value
                                if isinstance(item, dict)
                            ]
                    except (TypeError, ValueError, IndexError):
                        pass

                # Handle UUID fields
                elif field_type == uuid.UUID and isinstance(value, str):
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
                elif actual_type == datetime and isinstance(value, str):
                    try:
                        obj_dict[key] = datetime.fromisoformat(value)
                    except ValueError:
                        pass

                # Handle enum fields
                elif (
                    inspect.isclass(actual_type)
                    and issubclass(actual_type, Enum)
                    and isinstance(value, (str, int))
                ):
                    try:
                        obj_dict[key] = actual_type(value)
                    except (ValueError, KeyError):
                        pass

                # Handle nested dataclass fields
                elif (
                    inspect.isclass(actual_type)
                    and hasattr(actual_type, "__dataclass_fields__")
                    and isinstance(value, dict)
                ):
                    try:
                        # Get type hints for the nested dataclass
                        nested_type_hints = get_type_hints(actual_type)
                        # Recursively process the nested dictionary with decremented depth
                        nested_dict = JsonSerializer.object_hook_with_types(
                            value, nested_type_hints, max_depth - 1
                        )
                        # Create the dataclass instance
                        obj_dict[key] = actual_type(**nested_dict)
                    except (TypeError, ValueError):
                        pass

        return obj_dict


class JsonDB(Generic[T]):
    """A simple JSON file-based database for dataclasses."""

    def __init__(self, data_class: Type[T], file_path: Path):
        """
        Initialize the database with a dataclass type and file path.

        Args:
            data_class: The dataclass type this database will store
            file_path: Path to the JSON file
        """
        self.data_class = data_class
        self.file_path = file_path
        self.data: List[T] = []

        # Extract type hints from the dataclass
        self.type_hints = get_type_hints(data_class)

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
        """
        Save data to the JSON file.

        Serialization happens fully in memory before the file is opened, so an
        item that cannot be encoded raises without truncating the existing file.

        Raises:
            JsonDBException: If any item cannot be serialized to JSON.
        """
        try:
            payload = json.dumps(
                [asdict(item) for item in items],
                indent=2,
                default=JsonSerializer.default,
            )
        except (TypeError, ValueError, OverflowError, RecursionError) as e:
            raise JsonDBException(f"Error serializing to JSON: {e}") from e

        with open(self.file_path, "w", encoding="utf-8") as f:
            f.write(payload)

    def _dict_to_dataclass(self, data_dict: Dict[str, Any]) -> T:
        """Convert a dictionary to the specified dataclass."""
        return self.data_class(**data_dict)

    def save(self) -> None:
        """Save current data to the file."""
        self._save(self.data)

    def _save_or_rollback(self, snapshot: List[T]) -> None:
        """
        Save current data, restoring `snapshot` if serialization fails.

        Serialization leaves the file untouched when it fails, so the in-memory
        data must be rewound too or the two would disagree and every later save
        would fail on the same unserializable item.

        Only serialization failures roll back. An I/O error while writing
        propagates as-is, leaving `self.data` modified, because the file may
        already be partially written and no in-memory state matches it.

        Args:
            snapshot: The item list to restore if serialization fails.

        Raises:
            JsonDBException: If the data cannot be serialized, after rolling back.
            OSError: If the file cannot be written, without rolling back.
        """
        try:
            self.save()
        except JsonDBException:
            self.data = snapshot
            self._after_rollback()
            raise

    def _after_rollback(self) -> None:
        """Restore state derived from `self.data` after a rollback. No-op here."""

    def all(self) -> List[T]:
        """Get all items."""
        return self.data.copy()

    def __len__(self) -> int:
        """Return the number of items in the database."""
        return len(self.data)

    def __iter__(self) -> Iterator[T]:
        """Iterate over the items in the database."""
        return iter(self.data)

    def __contains__(self, item: object) -> bool:
        """Return True if the given item is stored in the database."""
        return item in self.data

    @staticmethod
    def _matches(item: T, criteria: Dict[str, Any]) -> bool:
        """Return True if the item matches every field/value pair in criteria."""
        return all(
            hasattr(item, key) and getattr(item, key) == value
            for key, value in criteria.items()
        )

    def find(self, **kwargs: Any) -> List[T]:
        """Find items matching the given criteria."""
        if not kwargs:
            raise JsonDBException(
                "find() requires at least one search criterion. Use all() to get all items."
            )

        # Linear search for all criteria
        return [item for item in self.data if self._matches(item, kwargs)]

    def count(self, **kwargs: Any) -> int:
        """
        Count items, optionally filtered by criteria.

        Args:
            **kwargs: Optional field/value pairs to match. With no criteria,
                counts all items.

        Returns:
            The number of matching items.
        """
        if not kwargs:
            return len(self.data)

        return sum(1 for item in self.data if self._matches(item, kwargs))

    def delete(self, **kwargs: Any) -> int:
        """
        Delete all items matching the given criteria.

        Args:
            **kwargs: Field/value pairs an item must match to be deleted.

        Returns:
            The number of items deleted.

        Raises:
            JsonDBException: If no criteria are provided.
        """
        if not kwargs:
            raise JsonDBException(
                "delete() requires at least one criterion to avoid accidentally "
                "deleting all items."
            )

        kept: List[T] = []
        deleted = 0
        for item in self.data:
            if self._matches(item, kwargs):
                deleted += 1
            else:
                kept.append(item)

        if deleted:
            snapshot = self.data
            self.data = kept
            self._save_or_rollback(snapshot)

        return deleted

    def add(self, item: T) -> T:
        """
        Add an item to the database.

        Args:
            item: The item to add, must be of the correct type

        Returns:
            The added item

        Raises:
            JsonDBException: If the item is not of the expected type, or cannot be
                serialized, in which case the database is left unchanged.
        """
        if not isinstance(item, self.data_class):
            raise JsonDBException(
                f"Item must be of type {self.data_class.__name__}, got {type(item).__name__}"
            )
        # Automatically set timestamps if item has created_at and/or updated_at fields
        now = datetime.now()
        updates = {}
        if hasattr(item, "created_at") and getattr(item, "created_at") is None:
            updates["created_at"] = now
        if hasattr(item, "updated_at") and getattr(item, "updated_at") is None:
            updates["updated_at"] = now

        if updates:
            item = replace(item, **updates)

        snapshot = list(self.data)
        self.data.append(item)
        self._save_or_rollback(snapshot)

        return item


class IndexedJsonDB(JsonDB[T], Generic[T, PK]):
    """A JSON file-based database for dataclasses with primary key support."""

    def __init__(self, data_class: Type[T], file_path: Path, primary_key: str):
        """
        Initialize the database with a dataclass type and file path.

        Args:
            data_class: The dataclass type this database will store
            file_path: Path to the JSON file
            primary_key: The field name to use as primary key (required)
        """
        # Validate primary key is not None, empty, or whitespace-only
        if primary_key is None:
            raise JsonDBException("Primary key cannot be None")
        if not primary_key or not primary_key.strip():
            raise JsonDBException("Primary key cannot be empty or whitespace-only")

        self.primary_key = primary_key

        # Primary key index for performance optimization
        self._primary_key_index: Dict[PK, int] = {}

        # Validate primary key exists in dataclass
        type_hints = get_type_hints(data_class)
        if primary_key not in type_hints:
            raise JsonDBException(
                f"Primary key '{primary_key}' not found in {data_class.__name__} fields"
            )

        # Initialize the parent class
        super().__init__(data_class, file_path)

        # Build primary key index
        self._rebuild_primary_key_index()

    def _after_rollback(self) -> None:
        """Rebuild the primary key index, whose positions follow `self.data`."""
        self._rebuild_primary_key_index()

    def get(self, key_value: PK) -> Optional[T]:
        """Get item by primary key value."""
        # Use primary key index for O(1) lookup
        if key_value in self._primary_key_index:
            item_index = self._primary_key_index[key_value]
            return self.data[item_index]

        return None

    def find(self, **kwargs: Any) -> List[T]:
        """Find items matching the given criteria."""
        if not kwargs:
            raise JsonDBException(
                "find() requires at least one search criterion. Use all() to get all items."
            )

        # Use primary key index if searching by primary key only
        if len(kwargs) == 1 and self.primary_key in kwargs:
            key_value = kwargs[self.primary_key]
            item = self.get(key_value)
            return [item] if item else []

        # Fall back to parent's linear search for other criteria
        return super().find(**kwargs)

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
        # Check if item has primary key
        if not hasattr(item, self.primary_key):
            raise JsonDBException(f"Item must have a '{self.primary_key}' attribute")

        # Check for primary key uniqueness
        key_value = getattr(item, self.primary_key)
        if self.get(key_value) is not None:
            raise JsonDBException(
                f"Item with {self.primary_key}='{key_value}' already exists"
            )

        # Call parent's add method
        result = super().add(item)

        # Update primary key index
        key_value = getattr(item, self.primary_key)
        self._primary_key_index[key_value] = len(self.data) - 1

        return result

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
        if not isinstance(item, self.data_class):
            raise JsonDBException(
                f"Item must be of type {self.data_class.__name__}, got {type(item).__name__}"
            )

        if not hasattr(item, self.primary_key):
            raise JsonDBException(f"Item must have a '{self.primary_key}' attribute")

        # Update the updated_at timestamp if item has it
        if hasattr(item, "updated_at"):
            item = replace(item, updated_at=datetime.now())

        key_value = getattr(item, self.primary_key)
        for i, existing_item in enumerate(self.data):
            if (
                hasattr(existing_item, self.primary_key)
                and getattr(existing_item, self.primary_key) == key_value
            ):
                snapshot = list(self.data)
                self.data[i] = item
                self._save_or_rollback(snapshot)
                return item

        raise JsonDBException(f"Item with {self.primary_key}='{key_value}' not found")

    def delete(self, **kwargs: Any) -> int:
        """
        Delete all items matching the given criteria.

        Args:
            **kwargs: Field/value pairs an item must match to be deleted.

        Returns:
            The number of items deleted.

        Raises:
            JsonDBException: If no criteria are provided.
        """
        # Fast-path primary-key-only deletion via the O(1) index, mirroring find().
        # remove() already updates the index and saves.
        if len(kwargs) == 1 and self.primary_key in kwargs:
            return 1 if self.remove(kwargs[self.primary_key]) else 0

        deleted = super().delete(**kwargs)

        # Indices may have shifted, so rebuild the primary key index.
        if deleted:
            self._rebuild_primary_key_index()

        return deleted

    def remove(self, key_value: PK) -> bool:
        """Remove an item by primary key value."""
        for i, item in enumerate(self.data):
            if (
                hasattr(item, self.primary_key)
                and getattr(item, self.primary_key) == key_value
            ):
                snapshot = list(self.data)
                self.data.pop(i)
                self._save_or_rollback(snapshot)

                # Rebuild primary key index since indices have shifted. A failed
                # save rebuilds it from the restored items instead.
                self._rebuild_primary_key_index()
                return True
        return False

    def _rebuild_primary_key_index(self) -> None:
        """Rebuild the primary key index for fast lookups."""
        self._primary_key_index = {}
        for i, item in enumerate(self.data):
            if hasattr(item, self.primary_key):
                key_value = getattr(item, self.primary_key)
                self._primary_key_index[key_value] = i
