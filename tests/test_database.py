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
    db = JsonDB(TestItem, temp_db_path, primary_key="id")

    # Add multiple items
    for i in range(3):
        item = TestItem(
            id=uuid.uuid4(), name=f"Item {i}", status=TestStatus.ACTIVE, quantity=i + 1
        )
        db.add(item)

    return db


@pytest.fixture
def populated_db_no_pk(temp_db_path):
    """Create a database without a primary key with some test items."""
    db = JsonDB(TestItem, temp_db_path)  # No primary key

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

    def test_init_with_primary_key(self, temp_db_path):
        """Test initializing a JsonDB with a primary key."""
        db = JsonDB(TestItem, temp_db_path, primary_key="id")
        assert db.primary_key == "id"

    def test_init_with_invalid_primary_key(self, temp_db_path):
        """Test initializing a JsonDB with an invalid primary key."""
        with pytest.raises(JsonDBException) as exc_info:
            JsonDB(TestItem, temp_db_path, primary_key="nonexistent_field")

        assert "Primary key 'nonexistent_field' not found in TestItem fields" in str(
            exc_info.value
        )

    def test_init_without_primary_key(self, temp_db_path):
        """Test initializing a JsonDB without a primary key."""
        db = JsonDB(TestItem, temp_db_path)
        assert db.primary_key is None

    def test_add_item_with_primary_key(self, temp_db_path, sample_item):
        """Test adding an item to the database."""
        db = JsonDB(TestItem, temp_db_path, primary_key="id")
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

    def test_add_item_without_primary_key(self, temp_db_path, sample_item):
        """Test adding an item to a database without a primary key."""
        db = JsonDB(TestItem, temp_db_path)  # No primary key
        db.add(sample_item)

        # Check that the item was added to memory
        assert len(db.data) == 1
        assert db.data[0] == sample_item

    def test_add_duplicate_primary_key(self, temp_db_path, sample_item):
        """Test adding an item with a duplicate primary key."""
        db = JsonDB(TestItem, temp_db_path, primary_key="id")
        db.add(sample_item)

        # Try to add another item with the same ID
        duplicate_item = TestItem(
            id=sample_item.id,
            name="Duplicate Item",
            status=TestStatus.ACTIVE,
            quantity=10,
        )

        with pytest.raises(JsonDBException) as exc_info:
            db.add(duplicate_item)

        assert f"Item with id='{sample_item.id}' already exists" in str(exc_info.value)

    def test_add_wrong_type(self, temp_db_path):
        """Test that adding an item of the wrong type raises an exception."""
        db = JsonDB(TestItem, temp_db_path, primary_key="id")

        @dataclass
        class OtherItem:
            id: int
            name: str

        with pytest.raises(JsonDBException) as exc_info:
            db.add(OtherItem(id=1, name="Wrong Type"))

        assert "must be of type TestItem" in str(exc_info.value)

    def test_get_item_with_primary_key(self, temp_db_path, sample_item):
        """Test retrieving an item by ID."""
        db = JsonDB(TestItem, temp_db_path, primary_key="id")
        db.add(sample_item)

        # Get the item
        result = db.get(sample_item.id)

        # Check that the correct item was returned
        assert result is not None
        assert result.id == sample_item.id
        assert result.name == sample_item.name
        assert result.status == sample_item.status

    def test_get_item_no_primary_key(self, temp_db_path, sample_item):
        """Test retrieving an item when no primary key is configured."""
        db = JsonDB(TestItem, temp_db_path)  # No primary key
        db.add(sample_item)

        # Try to get an item - should raise an exception
        with pytest.raises(JsonDBException) as exc_info:
            db.get(sample_item.id)

        assert "Cannot use get() without a primary key configured" in str(
            exc_info.value
        )

    def test_get_nonexistent_item(self, temp_db_path):
        """Test retrieving a nonexistent item."""
        db = JsonDB(TestItem, temp_db_path, primary_key="id")

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

    def test_find_items_no_primary_key(self, populated_db_no_pk):
        """Test finding items by criteria when no primary key is configured."""
        # Find items with status=ACTIVE
        results = populated_db_no_pk.find(status=TestStatus.ACTIVE)

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

    def test_find_requires_criteria(self, temp_db_path):
        """Test that find() requires search criteria."""
        db = JsonDB(TestItem, temp_db_path, primary_key="id")

        # Add some test data
        item = TestItem(
            id=uuid.uuid4(), name="Test Item", status=TestStatus.ACTIVE, quantity=1
        )
        db.add(item)

        # Test that find() without criteria raises an error
        with pytest.raises(JsonDBException) as exc_info:
            db.find()
        assert "find() requires at least one search criterion" in str(exc_info.value)
        assert "Use all() to get all items" in str(exc_info.value)

        # Verify that find() with criteria still works
        results = db.find(status=TestStatus.ACTIVE)
        assert len(results) == 1
        assert results[0].name == "Test Item"

    def test_all_items_with_primary_key(self, populated_db):
        """Test retrieving all items."""
        # Get all items
        results = populated_db.all()

        # Check that all items were returned
        assert len(results) == 3

        # Check that a copy was returned (not the original list)
        assert results is not populated_db.data

    def test_all_items_no_primary_key(self, populated_db_no_pk):
        """Test retrieving all items when no primary key is configured."""
        # Get all items
        results = populated_db_no_pk.all()

        # Check that all items were returned
        assert len(results) == 3

        # Check that a copy was returned (not the original list)
        assert results is not populated_db_no_pk.data

    def test_update_item_with_primary_key(self, temp_db_path, sample_item):
        """Test updating an item."""
        db = JsonDB(TestItem, temp_db_path, primary_key="id")
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

    def test_update_item_no_primary_key(self, temp_db_path, sample_item):
        """Test updating an item when no primary key is configured."""
        db = JsonDB(TestItem, temp_db_path)  # No primary key
        db.add(sample_item)

        # Try to update an item - should raise an exception
        updated_item = TestItem(
            id=sample_item.id,
            name="Updated Item",
            status=TestStatus.COMPLETED,
            quantity=10,
        )

        with pytest.raises(JsonDBException) as exc_info:
            db.update(updated_item)

        assert "Cannot use update() without a primary key configured" in str(
            exc_info.value
        )

    def test_update_nonexistent_item(self, temp_db_path, sample_item):
        """Test updating a nonexistent item."""
        db = JsonDB(TestItem, temp_db_path, primary_key="id")

        # Try to update an item that doesn't exist
        with pytest.raises(JsonDBException) as exc_info:
            db.update(sample_item)

        assert f"Item with id='{sample_item.id}' not found" in str(exc_info.value)

    def test_update_wrong_type(self, temp_db_path, sample_item):
        """Test updating with an item of the wrong type."""
        db = JsonDB(TestItem, temp_db_path, primary_key="id")
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
        db = JsonDB(TestItem, temp_db_path, primary_key="id")

        @dataclass
        class NoIdItem:
            name: str

        # Try to update with an item that has no id
        with pytest.raises(JsonDBException) as exc_info:
            db.update(NoIdItem(name="No ID"))

        assert "must be of type TestItem" in str(exc_info.value)

    def test_remove_item_with_primary_key(self, temp_db_path, sample_item):
        """Test removing an item."""
        db = JsonDB(TestItem, temp_db_path, primary_key="id")
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

    def test_remove_item_no_primary_key(self, temp_db_path, sample_item):
        """Test removing an item when no primary key is configured."""
        db = JsonDB(TestItem, temp_db_path)  # No primary key
        db.add(sample_item)

        # Try to remove an item - should raise an exception
        with pytest.raises(JsonDBException) as exc_info:
            db.remove(sample_item.id)

        assert "Cannot use remove() without a primary key configured" in str(
            exc_info.value
        )

    def test_remove_nonexistent_item(self, temp_db_path):
        """Test removing a nonexistent item."""
        db = JsonDB(TestItem, temp_db_path, primary_key="id")

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
        db1 = JsonDB(TestItem, temp_db_path, primary_key="id")
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
        db2 = JsonDB(TestItem, temp_db_path, primary_key="id")

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
        db = JsonDB(TestItem, temp_db_path, primary_key="id")

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


class TestCustomPrimaryKey:
    """Test cases for custom primary keys (not 'id')."""

    @dataclass
    class CustomItem:
        custom_id: str
        name: str
        value: int

    def test_custom_primary_key(self, temp_db_path):
        """Test using a custom primary key field."""
        db = JsonDB(self.CustomItem, temp_db_path, primary_key="custom_id")

        item = self.CustomItem(custom_id="custom_123", name="Test Item", value=42)
        db.add(item)

        # Test retrieval
        found_item = db.get("custom_123")
        assert found_item is not None
        assert found_item.custom_id == "custom_123"
        assert found_item.name == "Test Item"

    def test_custom_primary_key_uniqueness(self, temp_db_path):
        """Test uniqueness enforcement with custom primary key."""
        db = JsonDB(self.CustomItem, temp_db_path, primary_key="custom_id")

        item1 = self.CustomItem(custom_id="same_id", name="First Item", value=1)
        item2 = self.CustomItem(custom_id="same_id", name="Second Item", value=2)

        db.add(item1)

        with pytest.raises(JsonDBException) as exc_info:
            db.add(item2)

        assert "Item with custom_id='same_id' already exists" in str(exc_info.value)

    def test_custom_primary_key_update(self, temp_db_path):
        """Test updating items with custom primary key."""
        db = JsonDB(self.CustomItem, temp_db_path, primary_key="custom_id")

        original_item = self.CustomItem(
            custom_id="update_test", name="Original", value=10
        )
        db.add(original_item)

        updated_item = self.CustomItem(
            custom_id="update_test", name="Updated", value=20
        )
        db.update(updated_item)

        # Verify update
        found_item = db.get("update_test")
        assert found_item.name == "Updated"
        assert found_item.value == 20

    def test_custom_primary_key_remove(self, temp_db_path):
        """Test removing items with custom primary key."""
        db = JsonDB(self.CustomItem, temp_db_path, primary_key="custom_id")

        item = self.CustomItem(custom_id="remove_test", name="To Remove", value=5)
        db.add(item)

        # Remove the item
        result = db.remove("remove_test")
        assert result is True

        # Verify removal
        found_item = db.get("remove_test")
        assert found_item is None


class TestPrimaryKeyEdgeCases:
    """Test edge cases and error conditions for primary keys."""

    @dataclass
    class ItemWithInt:
        pk: int
        name: str

    @dataclass
    class ItemWithOptional:
        id: uuid.UUID
        optional_field: str = "default"

    def test_integer_primary_key(self, temp_db_path):
        """Test using an integer as primary key."""
        db = JsonDB(self.ItemWithInt, temp_db_path, primary_key="pk")

        item = self.ItemWithInt(pk=123, name="Integer PK Test")
        db.add(item)

        found_item = db.get(123)
        assert found_item is not None
        assert found_item.pk == 123

    def test_primary_key_with_none_value(self, temp_db_path):
        """Test behavior when primary key value is None."""

        @dataclass
        class ItemWithNone:
            id: uuid.UUID
            name: str

        db = JsonDB(ItemWithNone, temp_db_path, primary_key="id")

        # Create item with None id
        item = ItemWithNone(id=None, name="None ID Test")

        # This should work - None is a valid value
        db.add(item)

        # Should be able to retrieve it
        found_item = db.get(None)
        assert found_item is not None
        assert found_item.name == "None ID Test"

    def test_serialization_with_custom_pk(self, temp_db_path):
        """Test serialization/deserialization round trip with custom primary key."""
        db1 = JsonDB(
            TestCustomPrimaryKey.CustomItem, temp_db_path, primary_key="custom_id"
        )

        original_item = TestCustomPrimaryKey.CustomItem(
            custom_id="serialize_test", name="Serialization Test", value=999
        )
        db1.add(original_item)

        # Create new database instance to test loading
        db2 = JsonDB(
            TestCustomPrimaryKey.CustomItem, temp_db_path, primary_key="custom_id"
        )

        loaded_item = db2.get("serialize_test")
        assert loaded_item is not None
        assert loaded_item.custom_id == "serialize_test"
        assert loaded_item.name == "Serialization Test"
        assert loaded_item.value == 999

    def test_mixed_operations_with_and_without_pk(self, temp_db_path):
        """Test that databases with and without primary keys can coexist."""
        # First, create a database without primary key and add some data
        db_no_pk = JsonDB(TestItem, temp_db_path)
        item1 = TestItem(
            id=uuid.uuid4(), name="No PK Item", status=TestStatus.ACTIVE, quantity=1
        )
        db_no_pk.add(item1)

        # Now create a database with primary key on the same file
        db_with_pk = JsonDB(TestItem, temp_db_path, primary_key="id")

        # Should be able to load the existing data
        all_items = db_with_pk.all()
        assert len(all_items) == 1
        assert all_items[0].name == "No PK Item"

        # Should be able to retrieve the item by ID
        found_item = db_with_pk.get(item1.id)
        assert found_item is not None
        assert found_item.name == "No PK Item"

    def test_error_messages_clarity(self, temp_db_path):
        """Test that error messages are clear and helpful."""
        # Test invalid primary key
        with pytest.raises(JsonDBException) as exc_info:
            JsonDB(TestItem, temp_db_path, primary_key="nonexistent")
        assert "Primary key 'nonexistent' not found in TestItem fields" in str(
            exc_info.value
        )

        # Test operations without primary key
        db = JsonDB(TestItem, temp_db_path)  # No primary key

        with pytest.raises(JsonDBException) as exc_info:
            db.get("some_value")
        assert "Cannot use get() without a primary key configured" in str(
            exc_info.value
        )

        with pytest.raises(JsonDBException) as exc_info:
            db.update(
                TestItem(
                    id=uuid.uuid4(), name="test", status=TestStatus.ACTIVE, quantity=1
                )
            )
        assert "Cannot use update() without a primary key configured" in str(
            exc_info.value
        )

        with pytest.raises(JsonDBException) as exc_info:
            db.remove("some_value")
        assert "Cannot use remove() without a primary key configured" in str(
            exc_info.value
        )


class TestPrimaryKeyIndexing:
    """Test cases for primary key indexing performance optimization."""

    def test_primary_key_index_creation(self, temp_db_path):
        """Test that primary key index is automatically created."""
        db = JsonDB(TestItem, temp_db_path, primary_key="id")

        # Add some items
        items = []
        for i in range(5):
            item = TestItem(
                id=uuid.uuid4(),
                name=f"Item {i}",
                status=TestStatus.ACTIVE,
                quantity=i,
            )
            items.append(item)
            db.add(item)

        # Verify that the index contains all primary keys
        assert len(db._primary_key_index) == 5
        for item in items:
            assert item.id in db._primary_key_index

    def test_index_maintained_on_updates(self, temp_db_path):
        """Test that the index is properly maintained during updates."""
        db = JsonDB(TestItem, temp_db_path, primary_key="id")

        # Add initial items
        item1 = TestItem(
            id=uuid.uuid4(), name="Item 1", status=TestStatus.ACTIVE, quantity=1
        )
        item2 = TestItem(
            id=uuid.uuid4(), name="Item 2", status=TestStatus.ACTIVE, quantity=2
        )

        db.add(item1)
        db.add(item2)

        # Verify index state
        assert len(db._primary_key_index) == 2
        assert item1.id in db._primary_key_index
        assert item2.id in db._primary_key_index

        # Update an item
        updated_item1 = TestItem(
            id=item1.id, name="Updated Item 1", status=TestStatus.COMPLETED, quantity=10
        )
        db.update(updated_item1)

        # Verify index is still correct
        assert len(db._primary_key_index) == 2
        assert item1.id in db._primary_key_index
        assert item2.id in db._primary_key_index

        # Verify we can still get the updated item
        found_item = db.get(item1.id)
        assert found_item.name == "Updated Item 1"
        assert found_item.quantity == 10

    def test_index_maintained_on_removal(self, temp_db_path):
        """Test that the index is properly maintained during removals."""
        db = JsonDB(TestItem, temp_db_path, primary_key="id")

        # Add items
        item1 = TestItem(
            id=uuid.uuid4(), name="Item 1", status=TestStatus.ACTIVE, quantity=1
        )
        item2 = TestItem(
            id=uuid.uuid4(), name="Item 2", status=TestStatus.ACTIVE, quantity=2
        )
        item3 = TestItem(
            id=uuid.uuid4(), name="Item 3", status=TestStatus.ACTIVE, quantity=3
        )

        db.add(item1)
        db.add(item2)
        db.add(item3)

        # Verify initial index state
        assert len(db._primary_key_index) == 3

        # Remove middle item
        result = db.remove(item2.id)
        assert result is True

        # Verify index is updated
        assert len(db._primary_key_index) == 2
        assert item1.id in db._primary_key_index
        assert item2.id not in db._primary_key_index
        assert item3.id in db._primary_key_index

        # Verify we can still get remaining items
        found_item1 = db.get(item1.id)
        found_item3 = db.get(item3.id)
        assert found_item1 is not None
        assert found_item3 is not None

        # Verify removed item cannot be found
        found_item2 = db.get(item2.id)
        assert found_item2 is None

    def test_index_persistence_across_loads(self, temp_db_path):
        """Test that the index is rebuilt when loading from file."""
        # Create database and add items
        db1 = JsonDB(TestItem, temp_db_path, primary_key="id")

        item1 = TestItem(
            id=uuid.uuid4(), name="Item 1", status=TestStatus.ACTIVE, quantity=1
        )
        item2 = TestItem(
            id=uuid.uuid4(), name="Item 2", status=TestStatus.ACTIVE, quantity=2
        )

        db1.add(item1)
        db1.add(item2)

        # Create new database instance (simulates restart)
        db2 = JsonDB(TestItem, temp_db_path, primary_key="id")

        # Verify index was rebuilt
        assert len(db2._primary_key_index) == 2
        assert item1.id in db2._primary_key_index
        assert item2.id in db2._primary_key_index

        # Verify we can get items using the rebuilt index
        found_item1 = db2.get(item1.id)
        found_item2 = db2.get(item2.id)

        assert found_item1 is not None
        assert found_item2 is not None
        assert found_item1.name == "Item 1"
        assert found_item2.name == "Item 2"
