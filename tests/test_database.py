import json
import uuid
import pytest
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import get_type_hints

from src.typed_json_db import JsonDB, JsonDBException, JsonSerializer


class TestStatus(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"


@dataclass
class TestItem:
    id: uuid.UUID
    name: str
    status: TestStatus  # Now using proper Enum
    quantity: int


@pytest.fixture
def temp_db_path():
    """Create a temporary directory and database path for testing."""
    with TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_db.json"
        yield db_path


@pytest.fixture
def sample_item():
    """Create a sample TestItem for database operations."""
    return TestItem(
        id=uuid.uuid4(), name="Test Item", status=TestStatus.PENDING, quantity=5
    )


@pytest.fixture
def populated_db(temp_db_path):
    """Create a database with some test items."""
    db = JsonDB(TestItem, temp_db_path)

    # Add multiple items
    for i in range(3):
        item = TestItem(
            id=uuid.uuid4(), name=f"Item {i}", status=TestStatus.ACTIVE, quantity=i + 1
        )
        db.add(item)

    return db


class TestJsonSerializer:
    def test_default_uuid(self):
        """Test serialization of UUID objects."""
        test_uuid = uuid.uuid4()
        result = JsonSerializer.default(test_uuid)
        assert result == str(test_uuid)

    def test_default_enum(self):
        """Test serialization of Enum values."""
        result = JsonSerializer.default(TestStatus.ACTIVE)
        assert result == "active"

    def test_default_unsupported(self):
        """Test handling of unsupported types."""

        class UnsupportedType:
            pass

        with pytest.raises(TypeError):
            JsonSerializer.default(UnsupportedType())

    def test_object_hook_with_types(self):
        """Test deserialization with type hints."""
        # Get actual type hints from the TestItem class
        type_hints = get_type_hints(TestItem)

        # Create test data with fields matching TestItem
        test_uuid = uuid.uuid4()
        input_dict = {
            "id": str(test_uuid),
            "name": "Test Item",
            "status": "active",
            "quantity": 5,
        }

        # Process with object_hook_with_types
        result = JsonSerializer.object_hook_with_types(input_dict, type_hints)

        # Check type conversions
        assert isinstance(result["id"], uuid.UUID)
        assert result["id"] == test_uuid
        assert isinstance(result["status"], TestStatus)
        assert result["status"] == TestStatus.ACTIVE
        assert result["name"] == "Test Item"
        assert result["quantity"] == 5


class TestJsonDB:
    def test_init_creates_file(self, temp_db_path):
        """Test that initializing a JsonDB creates the file if it doesn't exist."""
        # The file should not exist yet
        assert not temp_db_path.exists()

        # Initialize the database
        JsonDB(TestItem, temp_db_path)

        # Check that the file was created
        assert temp_db_path.exists()

        # Check that it contains an empty array
        with open(temp_db_path, "r") as f:
            content = json.load(f)
            assert content == []

    def test_add_item(self, temp_db_path, sample_item):
        """Test adding an item to the database."""
        db = JsonDB(TestItem, temp_db_path)
        db.add(sample_item)

        # Check that the item was added to memory
        assert len(db.data) == 1
        assert db.data[0] == sample_item

        # Check that the item was saved to the file
        with open(temp_db_path, "r") as f:
            content = json.load(f)
            assert len(content) == 1
            assert content[0]["name"] == sample_item.name
            assert content[0]["id"] == str(sample_item.id)
            assert content[0]["status"] == "pending"  # Serialized as string

    def test_add_wrong_type(self, temp_db_path):
        """Test that adding an item of the wrong type raises an exception."""
        db = JsonDB(TestItem, temp_db_path)

        @dataclass
        class OtherItem:
            id: int
            name: str

        with pytest.raises(JsonDBException) as exc_info:
            db.add(OtherItem(id=1, name="Wrong Type"))

        assert "must be of type TestItem" in str(exc_info.value)

    def test_get_item(self, temp_db_path, sample_item):
        """Test retrieving an item by ID."""
        db = JsonDB(TestItem, temp_db_path)
        db.add(sample_item)

        # Get the item
        result = db.get(sample_item.id)

        # Check that the correct item was returned
        assert result is not None
        assert result.id == sample_item.id
        assert result.name == sample_item.name
        assert result.status == sample_item.status

    def test_get_nonexistent_item(self, temp_db_path):
        """Test retrieving a nonexistent item."""
        db = JsonDB(TestItem, temp_db_path)

        # Get a nonexistent item
        result = db.get(uuid.uuid4())

        # Check that None was returned
        assert result is None

    def test_find_items(self, populated_db):
        """Test finding items by criteria."""
        # Find items with status=ACTIVE
        results = populated_db.find(status=TestStatus.ACTIVE)

        # Check that all items were found (all 3 items have status=ACTIVE)
        assert len(results) == 3

    def test_find_items_multiple_criteria(self, populated_db):
        """Test finding items by multiple criteria."""
        # Find items with status=ACTIVE and quantity=2
        results = populated_db.find(status=TestStatus.ACTIVE, quantity=2)

        # Check that only the matching item was found
        assert len(results) == 1
        assert results[0].quantity == 2

    def test_find_nonexistent_items(self, populated_db):
        """Test finding nonexistent items."""
        # Find items with status=COMPLETED (none have this status)
        results = populated_db.find(status=TestStatus.COMPLETED)

        # Check that no items were found
        assert len(results) == 0

    def test_all_items(self, populated_db):
        """Test retrieving all items."""
        # Get all items
        results = populated_db.all()

        # Check that all items were returned
        assert len(results) == 3

        # Check that a copy was returned (not the original list)
        assert results is not populated_db.data

    def test_update_item(self, temp_db_path, sample_item):
        """Test updating an item."""
        db = JsonDB(TestItem, temp_db_path)
        db.add(sample_item)

        # Update the item
        updated_item = TestItem(
            id=sample_item.id,
            name="Updated Item",
            status=TestStatus.COMPLETED,
            quantity=10,
        )
        db.update(updated_item)

        # Check that the item was updated in memory
        assert len(db.data) == 1
        assert db.data[0].name == "Updated Item"
        assert db.data[0].status == TestStatus.COMPLETED
        assert db.data[0].quantity == 10

        # Check that the item was updated in the file
        with open(temp_db_path, "r") as f:
            content = json.load(f)
            assert len(content) == 1
            assert content[0]["name"] == "Updated Item"
            assert content[0]["status"] == "completed"  # Serialized as string
            assert content[0]["quantity"] == 10

    def test_update_nonexistent_item(self, temp_db_path, sample_item):
        """Test updating a nonexistent item."""
        db = JsonDB(TestItem, temp_db_path)

        # Try to update an item that doesn't exist
        with pytest.raises(JsonDBException) as exc_info:
            db.update(sample_item)

        assert f"Item with id {sample_item.id} not found" in str(exc_info.value)

    def test_update_wrong_type(self, temp_db_path, sample_item):
        """Test updating with an item of the wrong type."""
        db = JsonDB(TestItem, temp_db_path)
        db.add(sample_item)

        @dataclass
        class OtherItem:
            id: uuid.UUID
            name: str

        # Try to update with an item of the wrong type
        with pytest.raises(JsonDBException) as exc_info:
            db.update(OtherItem(id=sample_item.id, name="Wrong Type"))

        assert "must be of type TestItem" in str(exc_info.value)

    def test_update_no_id(self, temp_db_path):
        """Test updating with an item that has no id attribute."""
        db = JsonDB(TestItem, temp_db_path)

        @dataclass
        class NoIdItem:
            name: str

        # Try to update with an item that has no id
        with pytest.raises(JsonDBException) as exc_info:
            db.update(NoIdItem(name="No ID"))

        assert "must be of type TestItem" in str(exc_info.value)

    def test_remove_item(self, temp_db_path, sample_item):
        """Test removing an item."""
        db = JsonDB(TestItem, temp_db_path)
        db.add(sample_item)

        # Remove the item
        result = db.remove(sample_item.id)

        # Check that the operation was successful
        assert result is True

        # Check that the item was removed from memory
        assert len(db.data) == 0

        # Check that the item was removed from the file
        with open(temp_db_path, "r") as f:
            content = json.load(f)
            assert len(content) == 0

    def test_remove_nonexistent_item(self, temp_db_path):
        """Test removing a nonexistent item."""
        db = JsonDB(TestItem, temp_db_path)

        # Try to remove an item that doesn't exist
        result = db.remove(uuid.uuid4())

        # Check that the operation was unsuccessful
        assert result is False

    def test_load_corrupt_json(self, temp_db_path):
        """Test loading from a corrupt JSON file."""
        # Create a corrupt JSON file
        with open(temp_db_path, "w") as f:
            f.write("{this is not valid json")

        # Try to initialize the database with the corrupt file
        with pytest.raises(JsonDBException) as exc_info:
            JsonDB(TestItem, temp_db_path)

        assert "Error parsing JSON file" in str(exc_info.value)

    def test_serialization_round_trip(self, temp_db_path, sample_item):
        """Test full serialization/deserialization round trip."""
        # Save the original ID for comparison
        original_id_str = str(sample_item.id)
        original_uuid = sample_item.id

        print(f"\nOriginal UUID: {original_uuid} (type: {type(original_uuid)})")
        print(f"Original UUID as string: {original_id_str}")

        # Initialize and add an item
        db1 = JsonDB(TestItem, temp_db_path)
        db1.add(sample_item)

        # Make sure the file exists and has content
        assert temp_db_path.exists()
        with open(temp_db_path, "r") as f:
            content = json.load(f)
            assert len(content) == 1
            saved_id = content[0]["id"]
            print(f"Saved ID in file: {saved_id} (type: {type(saved_id)})")
            assert saved_id == original_id_str

        # Re-initialize to test loading from file
        db2 = JsonDB(TestItem, temp_db_path)

        # Debug: print all items in db2
        all_items = db2.all()
        print(f"Number of items loaded: {len(all_items)}")
        for idx, item in enumerate(all_items):
            print(f"Item {idx} - ID: {item.id} (type: {type(item.id)})")

        # Try to get the item
        try_uuid = uuid.UUID(original_id_str)
        print(f"UUID for lookup: {try_uuid} (type: {type(try_uuid)})")

        # Get the loaded item
        loaded_item = db2.get(try_uuid)

        # Debug result
        if loaded_item is None:
            print("FAILURE: Item not found after reload!")
        else:
            print(f"SUCCESS: Item found with ID: {loaded_item.id}")

        # Check that the item was loaded
        assert loaded_item is not None

        # Check identity properties
        assert str(loaded_item.id) == original_id_str
        assert loaded_item.name == sample_item.name
        assert loaded_item.status == sample_item.status

    def test_uuid_comparison(self, temp_db_path):
        """Test that UUID comparison works correctly after serialization/deserialization."""
        test_id = uuid.uuid4()
        test_id_str = str(test_id)

        # Create a database
        db = JsonDB(TestItem, temp_db_path)

        # Add an item with the test ID
        item = TestItem(
            id=test_id, name="UUID Test", status=TestStatus.ACTIVE, quantity=1
        )
        db.add(item)

        # The get method should find the item using the original UUID
        found_item = db.get(test_id)
        assert found_item is not None
        assert found_item.id == test_id

        # The get method should also find the item using a new UUID created from the string representation
        recreated_uuid = uuid.UUID(test_id_str)
        found_item_2 = db.get(recreated_uuid)
        assert found_item_2 is not None
        assert found_item_2.id == test_id
        assert found_item_2.id == recreated_uuid

        # Direct comparison of the UUIDs should work
        assert test_id == recreated_uuid
