import json
import uuid
import pytest
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import get_type_hints, Any, Optional

from src.typed_json_db import JsonDB, IndexedJsonDB, JsonDBException, JsonSerializer
from src.typed_json_db import database as database_module


class ItemStatus(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"


@dataclass
class SampleItem:
    id: uuid.UUID
    name: str
    status: ItemStatus  # Now using proper Enum
    quantity: int


@pytest.fixture
def temp_db_path():
    """Create a temporary directory and database path for testing."""
    with TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_db.json"
        yield db_path


@pytest.fixture
def sample_item():
    """Create a sample SampleItem for database operations."""
    return SampleItem(
        id=uuid.uuid4(), name="Test Item", status=ItemStatus.PENDING, quantity=5
    )


@pytest.fixture
def populated_db(temp_db_path):
    """Create a database with some test items."""
    db: IndexedJsonDB[SampleItem, uuid.UUID] = IndexedJsonDB(
        SampleItem, temp_db_path, primary_key="id"
    )

    # Add multiple items
    for i in range(3):
        item = SampleItem(
            id=uuid.uuid4(), name=f"Item {i}", status=ItemStatus.ACTIVE, quantity=i + 1
        )
        db.add(item)

    return db


@pytest.fixture
def populated_db_no_pk(temp_db_path):
    """Create a database without a primary key with some test items."""
    db: JsonDB[SampleItem, Any] = JsonDB(SampleItem, temp_db_path)  # No primary key

    # Add multiple items
    for i in range(3):
        item = SampleItem(
            id=uuid.uuid4(), name=f"Item {i}", status=ItemStatus.ACTIVE, quantity=i + 1
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
        result = JsonSerializer.default(ItemStatus.ACTIVE)
        assert result == "active"

    def test_default_unsupported(self):
        """Test handling of unsupported types."""

        class UnsupportedType:
            pass

        with pytest.raises(TypeError):
            JsonSerializer.default(UnsupportedType())

    def test_object_hook_with_types(self):
        """Test deserialization with type hints."""
        # Get actual type hints from the SampleItem class
        type_hints = get_type_hints(SampleItem)

        # Create test data with fields matching SampleItem
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
        assert isinstance(result["status"], ItemStatus)
        assert result["status"] == ItemStatus.ACTIVE
        assert result["name"] == "Test Item"
        assert result["quantity"] == 5


class TestJsonDB:
    def test_init_creates_file(self, temp_db_path):
        """Test that initializing a JsonDB creates the file if it doesn't exist."""
        # The file should not exist yet
        assert not temp_db_path.exists()

        # Initialize the database
        JsonDB(SampleItem, temp_db_path)

        # Check that the file was created
        assert temp_db_path.exists()

        # Check that it contains an empty array
        with open(temp_db_path, "r") as f:
            content = json.load(f)
            assert content == []

    def test_init_with_primary_key(self, temp_db_path):
        """Test initializing a JsonDB with a primary key."""
        db = IndexedJsonDB(SampleItem, temp_db_path, primary_key="id")
        assert db.primary_key == "id"

    def test_init_with_invalid_primary_key(self, temp_db_path):
        """Test initializing a JsonDB with an invalid primary key."""
        with pytest.raises(JsonDBException) as exc_info:
            IndexedJsonDB(SampleItem, temp_db_path, primary_key="nonexistent_field")

        assert "Primary key 'nonexistent_field' not found in SampleItem fields" in str(
            exc_info.value
        )

    def test_init_with_empty_primary_key(self, temp_db_path):
        """Test initializing IndexedJsonDB with an empty primary key."""
        with pytest.raises(JsonDBException) as exc_info:
            IndexedJsonDB(SampleItem, temp_db_path, primary_key="")

        assert "Primary key cannot be empty or whitespace-only" in str(exc_info.value)

    def test_init_with_whitespace_primary_key(self, temp_db_path):
        """Test initializing IndexedJsonDB with a whitespace-only primary key."""
        with pytest.raises(JsonDBException) as exc_info:
            IndexedJsonDB(SampleItem, temp_db_path, primary_key="   ")

        assert "Primary key cannot be empty or whitespace-only" in str(exc_info.value)

    def test_init_with_none_primary_key(self, temp_db_path):
        """Test initializing IndexedJsonDB with None as primary key."""
        with pytest.raises(JsonDBException) as exc_info:
            IndexedJsonDB(SampleItem, temp_db_path, primary_key=None)

        assert "Primary key cannot be None" in str(exc_info.value)

    def test_init_without_primary_key(self, temp_db_path):
        """Test initializing a JsonDB without a primary key."""
        db = JsonDB(SampleItem, temp_db_path)
        assert not hasattr(db, "primary_key")

    def test_add_item_with_primary_key(self, temp_db_path, sample_item):
        """Test adding an item to the database."""
        db = IndexedJsonDB(SampleItem, temp_db_path, primary_key="id")
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
        db = JsonDB(SampleItem, temp_db_path)  # No primary key
        db.add(sample_item)

        # Check that the item was added to memory
        assert len(db.data) == 1
        assert db.data[0] == sample_item

    def test_add_duplicate_primary_key(self, temp_db_path, sample_item):
        """Test adding an item with a duplicate primary key."""
        db = IndexedJsonDB(SampleItem, temp_db_path, primary_key="id")
        db.add(sample_item)

        # Try to add another item with the same ID
        duplicate_item = SampleItem(
            id=sample_item.id,
            name="Duplicate Item",
            status=ItemStatus.ACTIVE,
            quantity=10,
        )

        with pytest.raises(JsonDBException) as exc_info:
            db.add(duplicate_item)

        assert f"Item with id='{sample_item.id}' already exists" in str(exc_info.value)

    def test_add_wrong_type(self, temp_db_path):
        """Test that adding an item of the wrong type raises an exception."""
        db = IndexedJsonDB(SampleItem, temp_db_path, primary_key="id")

        @dataclass
        class OtherItem:
            id: int
            name: str

        with pytest.raises(JsonDBException) as exc_info:
            db.add(OtherItem(id=1, name="Wrong Type"))

        assert "must be of type SampleItem" in str(exc_info.value)

    def test_get_item_with_primary_key(self, temp_db_path, sample_item):
        """Test retrieving an item by ID."""
        db = IndexedJsonDB(SampleItem, temp_db_path, primary_key="id")
        db.add(sample_item)

        # Get the item
        result = db.get(sample_item.id)

        # Check that the correct item was returned
        assert result is not None
        assert result.id == sample_item.id
        assert result.name == sample_item.name
        assert result.status == sample_item.status

    def test_get_item_no_primary_key(self, temp_db_path, sample_item):
        """Test that JsonDB doesn't have a get method since it has no primary key support."""
        db = JsonDB(SampleItem, temp_db_path)  # No primary key
        db.add(sample_item)

        # JsonDB should not have a get method
        assert not hasattr(db, "get")

    def test_get_nonexistent_item(self, temp_db_path):
        """Test retrieving a nonexistent item."""
        db = IndexedJsonDB(SampleItem, temp_db_path, primary_key="id")

        # Get a nonexistent item
        result = db.get(uuid.uuid4())

        # Check that None was returned
        assert result is None

    def test_find_items(self, populated_db):
        """Test finding items by criteria."""
        # Find items with status=ACTIVE
        results = populated_db.find(status=ItemStatus.ACTIVE)

        # Check that all items were found (all 3 items have status=ACTIVE)
        assert len(results) == 3

    def test_find_items_no_primary_key(self, populated_db_no_pk):
        """Test finding items by criteria when no primary key is configured."""
        # Find items with status=ACTIVE
        results = populated_db_no_pk.find(status=ItemStatus.ACTIVE)

        # Check that all items were found (all 3 items have status=ACTIVE)
        assert len(results) == 3

    def test_find_items_multiple_criteria(self, populated_db):
        """Test finding items by multiple criteria."""
        # Find items with status=ACTIVE and quantity=2
        results = populated_db.find(status=ItemStatus.ACTIVE, quantity=2)

        # Check that only the matching item was found
        assert len(results) == 1
        assert results[0].quantity == 2

    def test_find_nonexistent_items(self, populated_db):
        """Test finding nonexistent items."""
        # Find items with status=COMPLETED (none have this status)
        results = populated_db.find(status=ItemStatus.COMPLETED)

        # Check that no items were found
        assert len(results) == 0

    def test_find_requires_criteria(self, temp_db_path):
        """Test that find() requires search criteria."""
        db = IndexedJsonDB(SampleItem, temp_db_path, primary_key="id")

        # Add some test data
        item = SampleItem(
            id=uuid.uuid4(), name="Test Item", status=ItemStatus.ACTIVE, quantity=1
        )
        db.add(item)

        # Test that find() without criteria raises an error
        with pytest.raises(JsonDBException) as exc_info:
            db.find()
        assert "find() requires at least one search criterion" in str(exc_info.value)
        assert "Use all() to get all items" in str(exc_info.value)

        # Verify that find() with criteria still works
        results = db.find(status=ItemStatus.ACTIVE)
        assert len(results) == 1
        assert results[0].name == "Test Item"

    def test_delete_items(self, populated_db_no_pk):
        """Test deleting items matching a single criterion."""
        deleted = populated_db_no_pk.delete(status=ItemStatus.ACTIVE)

        # All 3 items had status=ACTIVE
        assert deleted == 3
        assert len(populated_db_no_pk.data) == 0

        # Verify the change was persisted to disk
        with open(populated_db_no_pk.file_path, "r") as f:
            assert json.load(f) == []

    def test_delete_items_multiple_criteria(self, populated_db_no_pk):
        """Test deleting items matching multiple criteria."""
        deleted = populated_db_no_pk.delete(status=ItemStatus.ACTIVE, quantity=2)

        # Only one item has quantity=2
        assert deleted == 1
        assert len(populated_db_no_pk.data) == 2
        assert all(item.quantity != 2 for item in populated_db_no_pk.data)

    def test_delete_no_matches(self, populated_db_no_pk):
        """Test that deleting with no matches changes nothing."""
        deleted = populated_db_no_pk.delete(status=ItemStatus.COMPLETED)

        assert deleted == 0
        assert len(populated_db_no_pk.data) == 3

    def test_delete_requires_criteria(self, populated_db_no_pk):
        """Test that delete() requires at least one criterion."""
        with pytest.raises(JsonDBException) as exc_info:
            populated_db_no_pk.delete()

        assert "delete() requires at least one criterion" in str(exc_info.value)
        # Nothing should have been deleted
        assert len(populated_db_no_pk.data) == 3

    def test_delete_updates_primary_key_index(self, populated_db):
        """Test that delete() keeps the IndexedJsonDB primary key index in sync."""
        remaining = populated_db.find(quantity=1)[0]
        survivor_id = remaining.id

        deleted = populated_db.delete(quantity=2)
        assert deleted == 1

        # The index should still resolve the survivor and not the deleted item
        assert populated_db.get(survivor_id) is not None
        assert populated_db.get(survivor_id).id == survivor_id

        # Index entries must point at valid positions for every remaining item
        for item in populated_db.data:
            assert populated_db.get(item.id) is item

    def test_delete_by_primary_key(self, populated_db):
        """Test deleting by primary key only (fast-path via the index)."""
        target = populated_db.all()[0]

        deleted = populated_db.delete(id=target.id)

        assert deleted == 1
        assert populated_db.get(target.id) is None
        assert len(populated_db.data) == 2
        # Remaining items must still resolve through the index
        for item in populated_db.data:
            assert populated_db.get(item.id) is item

    def test_delete_by_nonexistent_primary_key(self, populated_db):
        """Test deleting by a primary key that does not exist."""
        deleted = populated_db.delete(id=uuid.uuid4())

        assert deleted == 0
        assert len(populated_db.data) == 3

    def test_count_all(self, populated_db_no_pk):
        """Test counting all items with no criteria."""
        assert populated_db_no_pk.count() == 3

    def test_count_empty_db(self, temp_db_path):
        """Test counting an empty database."""
        db = JsonDB(SampleItem, temp_db_path)
        assert db.count() == 0

    def test_count_with_criteria(self, populated_db_no_pk):
        """Test counting items matching criteria."""
        assert populated_db_no_pk.count(status=ItemStatus.ACTIVE) == 3
        assert populated_db_no_pk.count(quantity=2) == 1
        assert populated_db_no_pk.count(status=ItemStatus.COMPLETED) == 0

    def test_len(self, populated_db_no_pk):
        """Test that len() returns the number of items."""
        assert len(populated_db_no_pk) == 3

    def test_len_empty_db(self, temp_db_path):
        """Test that len() is zero for an empty database."""
        db = JsonDB(SampleItem, temp_db_path)
        assert len(db) == 0

    def test_iter(self, populated_db_no_pk):
        """Test iterating over the database yields all items."""
        items = list(populated_db_no_pk)
        assert len(items) == 3
        assert items == populated_db_no_pk.all()

    def test_contains(self, temp_db_path, sample_item):
        """Test membership testing with the `in` operator."""
        db = JsonDB(SampleItem, temp_db_path)
        db.add(sample_item)

        assert sample_item in db

        other = SampleItem(
            id=uuid.uuid4(), name="Other", status=ItemStatus.ACTIVE, quantity=1
        )
        assert other not in db

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
        db = IndexedJsonDB(SampleItem, temp_db_path, primary_key="id")
        db.add(sample_item)

        # Update the item
        updated_item = SampleItem(
            id=sample_item.id,
            name="Updated Item",
            status=ItemStatus.COMPLETED,
            quantity=10,
        )
        db.update(updated_item)

        # Check that the item was updated in memory
        assert len(db.data) == 1
        assert db.data[0].name == "Updated Item"
        assert db.data[0].status == ItemStatus.COMPLETED
        assert db.data[0].quantity == 10

        # Check that the item was updated in the file
        with open(temp_db_path, "r") as f:
            content = json.load(f)
            assert len(content) == 1
            assert content[0]["name"] == "Updated Item"
            assert content[0]["status"] == "completed"  # Serialized as string
            assert content[0]["quantity"] == 10

    def test_update_item_no_primary_key(self, temp_db_path, sample_item):
        """Test that JsonDB doesn't have an update method since it has no primary key support."""
        db = JsonDB(SampleItem, temp_db_path)  # No primary key
        db.add(sample_item)

        # JsonDB should not have an update method
        assert not hasattr(db, "update")

    def test_update_nonexistent_item(self, temp_db_path, sample_item):
        """Test updating a nonexistent item."""
        db = IndexedJsonDB(SampleItem, temp_db_path, primary_key="id")

        # Try to update an item that doesn't exist
        with pytest.raises(JsonDBException) as exc_info:
            db.update(sample_item)

        assert f"Item with id='{sample_item.id}' not found" in str(exc_info.value)

    def test_update_wrong_type(self, temp_db_path, sample_item):
        """Test updating with an item of the wrong type."""
        db = IndexedJsonDB(SampleItem, temp_db_path, primary_key="id")
        db.add(sample_item)

        @dataclass
        class OtherItem:
            id: uuid.UUID
            name: str

        # Try to update with an item of the wrong type
        with pytest.raises(JsonDBException) as exc_info:
            db.update(OtherItem(id=sample_item.id, name="Wrong Type"))

        assert "must be of type SampleItem" in str(exc_info.value)

    def test_update_no_id(self, temp_db_path):
        """Test updating with an item that has no id attribute."""
        db = IndexedJsonDB(SampleItem, temp_db_path, primary_key="id")

        @dataclass
        class NoIdItem:
            name: str

        # Try to update with an item that has no id
        with pytest.raises(JsonDBException) as exc_info:
            db.update(NoIdItem(name="No ID"))

        assert "must be of type SampleItem" in str(exc_info.value)

    def test_remove_item_with_primary_key(self, temp_db_path, sample_item):
        """Test removing an item."""
        db = IndexedJsonDB(SampleItem, temp_db_path, primary_key="id")
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
        """Test that JsonDB doesn't have a remove method since it has no primary key support."""
        db = JsonDB(SampleItem, temp_db_path)  # No primary key
        db.add(sample_item)

        # JsonDB should not have a remove method
        assert not hasattr(db, "remove")

    def test_remove_nonexistent_item(self, temp_db_path):
        """Test removing a nonexistent item."""
        db = IndexedJsonDB(SampleItem, temp_db_path, primary_key="id")

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
            JsonDB(SampleItem, temp_db_path)

        assert "Error parsing JSON file" in str(exc_info.value)

    def test_serialization_round_trip(self, temp_db_path, sample_item):
        """Test full serialization/deserialization round trip."""
        # Save the original ID for comparison
        original_id_str = str(sample_item.id)
        original_uuid = sample_item.id

        print(f"\nOriginal UUID: {original_uuid} (type: {type(original_uuid)})")
        print(f"Original UUID as string: {original_id_str}")

        # Initialize and add an item
        db1 = IndexedJsonDB(SampleItem, temp_db_path, primary_key="id")
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
        db2 = IndexedJsonDB(SampleItem, temp_db_path, primary_key="id")

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
        db = IndexedJsonDB(SampleItem, temp_db_path, primary_key="id")

        # Add an item with the test ID
        item = SampleItem(
            id=test_id, name="UUID Test", status=ItemStatus.ACTIVE, quantity=1
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

    def test_nested_dataclasses_serialization(self, temp_db_path):
        """Test that nested dataclasses are properly serialized and deserialized."""

        @dataclass
        class Address:
            street: str
            city: str
            postal_code: str
            country: str = "USA"

        @dataclass
        class Contact:
            email: str
            phone: str

        @dataclass
        class Person:
            id: uuid.UUID
            name: str
            address: Address
            contact: Contact
            tags: list[str]
            metadata: dict[str, str]

        # Create database with nested structure
        db = IndexedJsonDB(Person, temp_db_path, primary_key="id")

        # Create person with nested data
        person_id = uuid.uuid4()
        address = Address(
            street="123 Main St", city="Anytown", postal_code="12345", country="USA"
        )
        contact = Contact(email="john@example.com", phone="555-1234")

        person = Person(
            id=person_id,
            name="John Doe",
            address=address,
            contact=contact,
            tags=["employee", "manager"],
            metadata={"department": "engineering", "level": "senior"},
        )

        # Add to database
        db.add(person)

        # Retrieve and verify all nested data is preserved
        retrieved = db.get(person_id)
        assert retrieved is not None
        assert retrieved.id == person_id
        assert retrieved.name == "John Doe"

        # Verify nested Address dataclass
        assert isinstance(retrieved.address, Address)
        assert retrieved.address.street == "123 Main St"
        assert retrieved.address.city == "Anytown"
        assert retrieved.address.postal_code == "12345"
        assert retrieved.address.country == "USA"

        # Verify nested Contact dataclass
        assert isinstance(retrieved.contact, Contact)
        assert retrieved.contact.email == "john@example.com"
        assert retrieved.contact.phone == "555-1234"

        # Verify list and dict are preserved
        assert retrieved.tags == ["employee", "manager"]
        assert retrieved.metadata == {"department": "engineering", "level": "senior"}

        # Test serialization round trip by reloading database
        db2 = IndexedJsonDB(Person, temp_db_path, primary_key="id")
        reloaded = db2.get(person_id)
        assert reloaded is not None
        assert reloaded.address.street == "123 Main St"
        assert reloaded.contact.email == "john@example.com"
        assert reloaded.tags == ["employee", "manager"]

        # Test find operations work with nested data
        results = db2.find(name="John Doe")
        assert len(results) == 1
        assert results[0].address.city == "Anytown"

        # Test update with nested data
        reloaded.address.city = "New City"
        reloaded.contact.phone = "555-9999"
        reloaded.tags.append("senior")
        db2.update(reloaded)

        # Verify update persisted
        updated = db2.get(person_id)
        assert updated.address.city == "New City"
        assert updated.contact.phone == "555-9999"

    def test_list_of_dataclasses_serialization(self, temp_db_path):
        """Test that lists of dataclasses are properly serialized and deserialized."""

        @dataclass
        class Address:
            street: str
            city: str
            postal_code: str
            country: str = "USA"

        @dataclass
        class Contact:
            email: str
            phone: str
            is_primary: bool = True

        @dataclass
        class Organization:
            id: uuid.UUID
            name: str
            headquarters: Address
            contacts: list[Contact]  # List of dataclasses

        # Create database with list of dataclasses
        db = IndexedJsonDB(Organization, temp_db_path, primary_key="id")

        # Create an organization with a list of contacts
        org_id = uuid.uuid4()
        hq = Address(
            street="100 Corporate Way",
            city="Enterprise",
            postal_code="54321",
            country="USA",
        )

        contacts = [
            Contact(email="sales@example.com", phone="555-1000"),
            Contact(email="support@example.com", phone="555-2000", is_primary=False),
            Contact(email="info@example.com", phone="555-3000", is_primary=False),
        ]

        org = Organization(
            id=org_id, name="Example Corp", headquarters=hq, contacts=contacts
        )

        # Add to database
        db.add(org)

        # Retrieve and verify data is preserved
        retrieved = db.get(org_id)
        assert retrieved is not None
        assert retrieved.id == org_id
        assert retrieved.name == "Example Corp"

        # Verify nested Address dataclass
        assert isinstance(retrieved.headquarters, Address)
        assert retrieved.headquarters.street == "100 Corporate Way"
        assert retrieved.headquarters.city == "Enterprise"

        # Verify list of Contact dataclasses
        assert isinstance(retrieved.contacts, list)
        assert len(retrieved.contacts) == 3

        # Check each contact is properly deserialized
        for contact, expected_contact in zip(retrieved.contacts, contacts):
            assert isinstance(contact, Contact)
            assert contact.email == expected_contact.email
            assert contact.phone == expected_contact.phone
            assert contact.is_primary == expected_contact.is_primary

        # Test serialization round trip by reloading database
        db2 = IndexedJsonDB(Organization, temp_db_path, primary_key="id")
        reloaded = db2.get(org_id)
        assert reloaded is not None

        # Verify list of contacts is correctly preserved after reload
        assert len(reloaded.contacts) == 3
        assert isinstance(reloaded.contacts[0], Contact)
        assert reloaded.contacts[0].email == "sales@example.com"
        assert reloaded.contacts[0].is_primary is True
        assert reloaded.contacts[1].email == "support@example.com"
        assert reloaded.contacts[1].is_primary is False

        # Test find operations work with nested data
        results = db2.find(name="Example Corp")
        assert len(results) == 1
        assert len(results[0].contacts) == 3
        assert results[0].contacts[2].email == "info@example.com"


class TestCustomPrimaryKey:
    """Test cases for custom primary keys (not 'id')."""

    @dataclass
    class CustomItem:
        custom_id: str
        name: str
        value: int

    def test_custom_primary_key(self, temp_db_path):
        """Test using a custom primary key field."""
        db = IndexedJsonDB(self.CustomItem, temp_db_path, primary_key="custom_id")

        item = self.CustomItem(custom_id="custom_123", name="Test Item", value=42)
        db.add(item)

        # Test retrieval
        found_item = db.get("custom_123")
        assert found_item is not None
        assert found_item.custom_id == "custom_123"
        assert found_item.name == "Test Item"

    def test_custom_primary_key_uniqueness(self, temp_db_path):
        """Test uniqueness enforcement with custom primary key."""
        db = IndexedJsonDB(self.CustomItem, temp_db_path, primary_key="custom_id")

        item1 = self.CustomItem(custom_id="same_id", name="First Item", value=1)
        item2 = self.CustomItem(custom_id="same_id", name="Second Item", value=2)

        db.add(item1)

        with pytest.raises(JsonDBException) as exc_info:
            db.add(item2)

        assert "Item with custom_id='same_id' already exists" in str(exc_info.value)

    def test_custom_primary_key_update(self, temp_db_path):
        """Test updating items with custom primary key."""
        db = IndexedJsonDB(self.CustomItem, temp_db_path, primary_key="custom_id")

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
        db = IndexedJsonDB(self.CustomItem, temp_db_path, primary_key="custom_id")

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
        db = IndexedJsonDB(self.ItemWithInt, temp_db_path, primary_key="pk")

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

        db = IndexedJsonDB(ItemWithNone, temp_db_path, primary_key="id")

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
        db1 = IndexedJsonDB(
            TestCustomPrimaryKey.CustomItem, temp_db_path, primary_key="custom_id"
        )

        original_item = TestCustomPrimaryKey.CustomItem(
            custom_id="serialize_test", name="Serialization Test", value=999
        )
        db1.add(original_item)

        # Create new database instance to test loading
        db2 = IndexedJsonDB(
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
        db_no_pk = JsonDB(SampleItem, temp_db_path)
        item1 = SampleItem(
            id=uuid.uuid4(), name="No PK Item", status=ItemStatus.ACTIVE, quantity=1
        )
        db_no_pk.add(item1)

        # Now create a database with primary key on the same file
        db_with_pk = IndexedJsonDB(SampleItem, temp_db_path, primary_key="id")

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
            IndexedJsonDB(SampleItem, temp_db_path, primary_key="nonexistent")
        assert "Primary key 'nonexistent' not found in SampleItem fields" in str(
            exc_info.value
        )

        # Test that JsonDB doesn't have primary key methods
        db = JsonDB(SampleItem, temp_db_path)  # No primary key

        # JsonDB should not have these methods
        assert not hasattr(db, "get")
        assert not hasattr(db, "update")
        assert not hasattr(db, "remove")


class TestPrimaryKeyIndexing:
    """Test cases for primary key indexing performance optimization."""

    def test_primary_key_index_creation(self, temp_db_path):
        """Test that primary key index is automatically created."""
        db = IndexedJsonDB(SampleItem, temp_db_path, primary_key="id")

        # Add some items
        items = []
        for i in range(5):
            item = SampleItem(
                id=uuid.uuid4(),
                name=f"Item {i}",
                status=ItemStatus.ACTIVE,
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
        db = IndexedJsonDB(SampleItem, temp_db_path, primary_key="id")

        # Add initial items
        item1 = SampleItem(
            id=uuid.uuid4(), name="Item 1", status=ItemStatus.ACTIVE, quantity=1
        )
        item2 = SampleItem(
            id=uuid.uuid4(), name="Item 2", status=ItemStatus.ACTIVE, quantity=2
        )

        db.add(item1)
        db.add(item2)

        # Verify index state
        assert len(db._primary_key_index) == 2
        assert item1.id in db._primary_key_index
        assert item2.id in db._primary_key_index

        # Update an item
        updated_item1 = SampleItem(
            id=item1.id, name="Updated Item 1", status=ItemStatus.COMPLETED, quantity=10
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
        db = IndexedJsonDB(SampleItem, temp_db_path, primary_key="id")

        # Add items
        item1 = SampleItem(
            id=uuid.uuid4(), name="Item 1", status=ItemStatus.ACTIVE, quantity=1
        )
        item2 = SampleItem(
            id=uuid.uuid4(), name="Item 2", status=ItemStatus.ACTIVE, quantity=2
        )
        item3 = SampleItem(
            id=uuid.uuid4(), name="Item 3", status=ItemStatus.ACTIVE, quantity=3
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
        db1 = IndexedJsonDB(SampleItem, temp_db_path, primary_key="id")

        item1 = SampleItem(
            id=uuid.uuid4(), name="Item 1", status=ItemStatus.ACTIVE, quantity=1
        )
        item2 = SampleItem(
            id=uuid.uuid4(), name="Item 2", status=ItemStatus.ACTIVE, quantity=2
        )

        db1.add(item1)
        db1.add(item2)

        # Create new database instance (simulates restart)
        db2 = IndexedJsonDB(SampleItem, temp_db_path, primary_key="id")

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


class TestTypeSafety:
    """Test type safety features of the JsonDB with different primary key types."""

    def test_uuid_primary_key_typing(self, temp_db_path):
        """Test JsonDB with UUID primary key type annotation."""

        # Test with explicit type annotation
        db: JsonDB[SampleItem, uuid.UUID] = IndexedJsonDB(
            SampleItem, temp_db_path, primary_key="id"
        )

        # Add item
        item_id = uuid.uuid4()
        item = SampleItem(
            id=item_id, name="Test Item", status=ItemStatus.PENDING, quantity=1
        )
        db.add(item)

        # Retrieve by UUID - should work with type safety
        retrieved = db.get(item_id)
        assert retrieved is not None
        assert retrieved.id == item_id
        assert retrieved.name == "Test Item"

        # Remove by UUID
        assert db.remove(item_id) is True
        assert db.get(item_id) is None

    def test_string_primary_key_typing(self, temp_db_path):
        """Test JsonDB with string primary key type annotation."""

        @dataclass
        class Product:
            sku: str
            name: str
            price: float

        db: JsonDB[Product, str] = IndexedJsonDB(
            Product, temp_db_path, primary_key="sku"
        )

        # Add product
        product = Product(sku="ABC123", name="Widget", price=9.99)
        db.add(product)

        # Retrieve by string key
        retrieved = db.get("ABC123")
        assert retrieved is not None
        assert retrieved.sku == "ABC123"
        assert retrieved.name == "Widget"

        # Remove by string key
        assert db.remove("ABC123") is True
        assert db.get("ABC123") is None

    def test_integer_primary_key_typing(self, temp_db_path):
        """Test JsonDB with integer primary key type annotation."""

        @dataclass
        class Order:
            order_id: int
            customer: str
            total: float

        db: JsonDB[Order, int] = IndexedJsonDB(
            Order, temp_db_path, primary_key="order_id"
        )

        # Add order
        order = Order(order_id=12345, customer="John Doe", total=99.99)
        db.add(order)

        # Retrieve by integer key
        retrieved = db.get(12345)
        assert retrieved is not None
        assert retrieved.order_id == 12345
        assert retrieved.customer == "John Doe"

        # Remove by integer key
        assert db.remove(12345) is True
        assert db.get(12345) is None

    def test_mixed_type_usage(self, temp_db_path):
        """Test that type annotations work correctly in mixed scenarios."""
        from typing import Any

        # Database without primary key - uses Any
        db_no_pk: JsonDB[SampleItem, Any] = JsonDB(SampleItem, temp_db_path)

        item = SampleItem(
            id=uuid.uuid4(), name="Test", status=ItemStatus.PENDING, quantity=1
        )
        db_no_pk.add(item)

        # Should work fine without primary key operations
        all_items = db_no_pk.all()
        assert len(all_items) == 1
        assert all_items[0].name == "Test"

        # Search operations should work
        found_items = db_no_pk.find(name="Test")
        assert len(found_items) == 1

    def test_nested_dataclass_with_typing(self, temp_db_path):
        """Test type annotations with nested dataclasses."""
        from typing import List

        @dataclass
        class Address:
            street: str
            city: str
            zip_code: str

        @dataclass
        class Person:
            id: uuid.UUID
            name: str
            addresses: List[Address]
            age: int

        db: JsonDB[Person, uuid.UUID] = IndexedJsonDB(
            Person, temp_db_path, primary_key="id"
        )

        person_id = uuid.uuid4()
        person = Person(
            id=person_id,
            name="Alice Johnson",
            addresses=[
                Address("123 Main St", "Anytown", "12345"),
                Address("456 Oak Ave", "Other City", "67890"),
            ],
            age=30,
        )

        db.add(person)

        # Retrieve and verify nested structure
        retrieved = db.get(person_id)
        assert retrieved is not None
        assert retrieved.name == "Alice Johnson"
        assert len(retrieved.addresses) == 2
        assert isinstance(retrieved.addresses[0], Address)
        assert retrieved.addresses[0].street == "123 Main St"
        assert retrieved.addresses[1].city == "Other City"

    def test_generic_type_preservation(self, temp_db_path):
        """Test that generic types are preserved correctly."""
        # Create database with specific types
        db: JsonDB[SampleItem, uuid.UUID] = IndexedJsonDB(
            SampleItem, temp_db_path, primary_key="id"
        )

        # Verify type hints are available
        assert hasattr(db, "data_class")
        assert hasattr(db, "primary_key")
        assert hasattr(db, "type_hints")

        # The actual runtime behavior should be identical
        item_id = uuid.uuid4()
        item = SampleItem(
            id=item_id, name="Type Test", status=ItemStatus.ACTIVE, quantity=5
        )

        added_item = db.add(item)
        assert isinstance(added_item, SampleItem)
        assert added_item.id == item_id

        retrieved_item = db.get(item_id)
        assert isinstance(retrieved_item, SampleItem)
        assert retrieved_item.name == "Type Test"

    def test_primary_key_index_typing(self, temp_db_path):
        """Test that primary key index works correctly with typed keys."""
        db: JsonDB[SampleItem, uuid.UUID] = IndexedJsonDB(
            SampleItem, temp_db_path, primary_key="id"
        )

        # Add multiple items
        items = []
        for i in range(5):
            item_id = uuid.uuid4()
            item = SampleItem(
                id=item_id, name=f"Item {i}", status=ItemStatus.ACTIVE, quantity=i
            )
            items.append(item)
            db.add(item)

        # Verify index contains all UUID keys
        assert len(db._primary_key_index) == 5

        for item in items:
            # Key should be in index
            assert item.id in db._primary_key_index
            # Retrieval should be fast (O(1) lookup)
            retrieved = db.get(item.id)
            assert retrieved is not None
            assert retrieved.id == item.id


class TestTimestamped:
    """Tests for Timestamped model integration."""

    def test_add_with_timestamped_auto_sets_timestamps(self, temp_db_path):
        """Test that add() automatically sets created and updated timestamps."""
        from datetime import datetime
        from src.typed_json_db import Timestamped

        @dataclass
        class TimestampedItem(Timestamped):
            id: uuid.UUID
            name: str

        db: JsonDB[TimestampedItem] = JsonDB(TimestampedItem, temp_db_path)

        # Create item without timestamps
        item = TimestampedItem(id=uuid.uuid4(), name="Test")

        before_add = datetime.now()
        added_item = db.add(item)
        after_add = datetime.now()

        # Timestamps should be set
        assert added_item.created_at is not None
        assert added_item.updated_at is not None
        assert before_add <= added_item.created_at <= after_add
        assert before_add <= added_item.updated_at <= after_add

    def test_add_with_timestamped_preserves_existing_timestamps(self, temp_db_path):
        """Test that add() preserves timestamps if already set."""
        from datetime import datetime, timedelta
        from src.typed_json_db import Timestamped

        @dataclass
        class TimestampedItem(Timestamped):
            id: uuid.UUID
            name: str

        db: JsonDB[TimestampedItem] = JsonDB(TimestampedItem, temp_db_path)

        # Create item with specific timestamps
        past_time = datetime.now() - timedelta(days=1)
        item = TimestampedItem(
            id=uuid.uuid4(), name="Test", created_at=past_time, updated_at=past_time
        )

        added_item = db.add(item)

        # Original timestamps should be preserved
        assert added_item.created_at == past_time
        assert added_item.updated_at == past_time

    def test_update_with_timestamped_updates_timestamp(self, temp_db_path):
        """Test that update() automatically updates the updated timestamp."""
        from datetime import datetime
        from src.typed_json_db import Timestamped
        from time import sleep

        @dataclass
        class TimestampedItem(Timestamped):
            id: uuid.UUID
            name: str

        db: IndexedJsonDB[TimestampedItem, uuid.UUID] = IndexedJsonDB(
            TimestampedItem, temp_db_path, primary_key="id"
        )

        # Add item
        item_id = uuid.uuid4()
        item = TimestampedItem(id=item_id, name="Original")
        added_item = db.add(item)

        original_created = added_item.created_at
        original_updated = added_item.updated_at

        # Small delay to ensure timestamp difference
        sleep(0.01)

        # Update item
        updated_item = TimestampedItem(
            id=item_id,
            name="Updated",
            created_at=original_created,
            updated_at=original_updated,
        )

        before_update = datetime.now()
        result = db.update(updated_item)
        after_update = datetime.now()

        # created_at should remain the same, updated_at should be new
        assert result.created_at == original_created
        assert result.updated_at != original_updated
        assert before_update <= result.updated_at <= after_update

    def test_timestamped_persistence(self, temp_db_path):
        """Test that timestamps are correctly saved and loaded from JSON."""
        from src.typed_json_db import Timestamped

        @dataclass
        class TimestampedItem(Timestamped):
            id: uuid.UUID
            name: str

        # Create and add item
        db1: IndexedJsonDB[TimestampedItem, uuid.UUID] = IndexedJsonDB(
            TimestampedItem, temp_db_path, primary_key="id"
        )
        item_id = uuid.uuid4()
        item = TimestampedItem(id=item_id, name="Test")
        added_item = db1.add(item)

        # Reload database
        db2: IndexedJsonDB[TimestampedItem, uuid.UUID] = IndexedJsonDB(
            TimestampedItem, temp_db_path, primary_key="id"
        )

        retrieved_item = db2.get(item_id)
        assert retrieved_item is not None
        assert retrieved_item.created_at == added_item.created_at
        assert retrieved_item.updated_at == added_item.updated_at

    def test_non_timestamped_class_unaffected(self, temp_db_path, sample_item):
        """Test that non-Timestamped classes are not affected by timestamp logic."""
        db: JsonDB[SampleItem] = JsonDB(SampleItem, temp_db_path)

        # SampleItem doesn't inherit from Timestamped
        added_item = db.add(sample_item)

        # Should not have created_at or updated_at fields
        assert not hasattr(added_item, "created_at")
        assert not hasattr(added_item, "updated_at")


@dataclass
class PayloadItem:
    """Item with an untyped payload field, used to trigger serialization errors."""

    name: str = ""
    payload: Optional[Any] = None


class TestSaveSerializationFailure:
    """A save that cannot be serialized must leave the existing file untouched."""

    @pytest.fixture
    def db_with_records(self, temp_db_path):
        """A database file holding two records that must survive a failed save."""
        db: JsonDB[PayloadItem] = JsonDB(PayloadItem, temp_db_path)
        db.add(PayloadItem(name="important-record-1"))
        db.add(PayloadItem(name="important-record-2"))
        return db

    @staticmethod
    def _assert_file_intact(temp_db_path, contents_before):
        """The file is unchanged, still valid JSON, and still openable."""
        assert temp_db_path.read_text(encoding="utf-8") == contents_before

        # Parseable as JSON, with both original records present
        parsed = json.loads(contents_before)
        assert [record["name"] for record in parsed] == [
            "important-record-1",
            "important-record-2",
        ]

        # A fresh database can still open the file and sees every prior record
        reopened: JsonDB[PayloadItem] = JsonDB(PayloadItem, temp_db_path)
        assert [item.name for item in reopened.all()] == [
            "important-record-1",
            "important-record-2",
        ]

    def test_unserializable_value_leaves_file_intact(
        self, temp_db_path, db_with_records
    ):
        """A value the serializer cannot encode (TypeError) must not corrupt the file."""
        contents_before = temp_db_path.read_text(encoding="utf-8")

        with pytest.raises(JsonDBException) as exc_info:
            db_with_records.add(PayloadItem(name="bad", payload=object()))

        assert "Error serializing to JSON" in str(exc_info.value)
        assert isinstance(exc_info.value.__cause__, TypeError)
        self._assert_file_intact(temp_db_path, contents_before)

    def test_circular_reference_leaves_file_intact(
        self, temp_db_path, db_with_records, monkeypatch
    ):
        """A circular reference (ValueError) must not corrupt the file either.

        A cycle built from plain containers cannot reach json.dumps on its own
        because asdict() recurses into them first and hits a RecursionError
        (covered by the test below), so the circular structure is injected where
        _save() builds its payload.
        """
        circular: dict = {"name": "bad"}
        circular["self"] = circular
        monkeypatch.setattr(database_module, "asdict", lambda item: circular)

        contents_before = temp_db_path.read_text(encoding="utf-8")

        with pytest.raises(JsonDBException) as exc_info:
            db_with_records.save()

        assert "Error serializing to JSON" in str(exc_info.value)
        assert isinstance(exc_info.value.__cause__, ValueError)
        monkeypatch.undo()
        self._assert_file_intact(temp_db_path, contents_before)

    def test_recursive_structure_leaves_file_intact(
        self, temp_db_path, db_with_records
    ):
        """A self-referential value exhausts the stack in asdict() before json sees it.

        The resulting RecursionError is wrapped too, so callers get a consistent
        exception type no matter which layer gives up on the value.
        """
        recursive: list = []
        recursive.append(recursive)
        contents_before = temp_db_path.read_text(encoding="utf-8")

        with pytest.raises(JsonDBException) as exc_info:
            db_with_records.add(PayloadItem(name="bad", payload=recursive))

        assert "Error serializing to JSON" in str(exc_info.value)
        assert isinstance(exc_info.value.__cause__, RecursionError)
        self._assert_file_intact(temp_db_path, contents_before)

    def test_on_disk_format_escapes_non_ascii(self, temp_db_path):
        """Successful saves keep the previous ASCII-escaped on-disk format."""
        db: JsonDB[PayloadItem] = JsonDB(PayloadItem, temp_db_path)
        db.add(PayloadItem(name="Ångström ✓"))

        raw = temp_db_path.read_bytes()
        assert raw.isascii()
        assert b"\\u00c5ngstr\\u00f6m" in raw

        reopened: JsonDB[PayloadItem] = JsonDB(PayloadItem, temp_db_path)
        assert reopened.all()[0].name == "Ångström ✓"


@dataclass
class KeyedPayloadItem:
    """Keyed item with an untyped payload, used to trigger serialization errors."""

    id: str = ""
    payload: Optional[Any] = None


class TestFailedSaveRollback:
    """A failed save must rewind memory so it keeps matching the file."""

    @pytest.fixture
    def keyed_db(self, temp_db_path):
        """An indexed database holding two keyed records."""
        db: IndexedJsonDB[KeyedPayloadItem, str] = IndexedJsonDB(
            KeyedPayloadItem, temp_db_path, primary_key="id"
        )
        db.add(KeyedPayloadItem(id="a"))
        db.add(KeyedPayloadItem(id="b"))
        return db

    def test_failed_add_leaves_database_usable(self, temp_db_path):
        """The rejected item is dropped from memory, so later saves still work."""
        db: JsonDB[PayloadItem] = JsonDB(PayloadItem, temp_db_path)
        db.add(PayloadItem(name="kept"))

        with pytest.raises(JsonDBException):
            db.add(PayloadItem(name="bad", payload=object()))

        # Memory matches the file rather than holding the unsaveable item
        assert len(db) == 1
        assert [item.name for item in db.all()] == ["kept"]

        # The database is not wedged: a later valid add still persists
        db.add(PayloadItem(name="later"))
        assert [
            record["name"]
            for record in json.loads(temp_db_path.read_text(encoding="utf-8"))
        ] == [
            "kept",
            "later",
        ]

    def test_failed_add_keeps_primary_key_index_consistent(
        self, keyed_db, temp_db_path
    ):
        """A rolled back add must not leave the key in data but missing from the index."""
        with pytest.raises(JsonDBException):
            keyed_db.add(KeyedPayloadItem(id="c", payload=object()))

        assert keyed_db.get("c") is None
        assert [item.id for item in keyed_db.all()] == ["a", "b"]

        # Because the key really is absent, re-adding it cannot duplicate it
        keyed_db.add(KeyedPayloadItem(id="c"))
        assert [
            record["id"]
            for record in json.loads(temp_db_path.read_text(encoding="utf-8"))
        ] == [
            "a",
            "b",
            "c",
        ]
        assert keyed_db.get("c") is not None

    def test_failed_update_keeps_previous_item(self, keyed_db, temp_db_path):
        """A failed update leaves the stored item in place."""
        contents_before = temp_db_path.read_text(encoding="utf-8")

        with pytest.raises(JsonDBException):
            keyed_db.update(KeyedPayloadItem(id="a", payload=object()))

        stored = keyed_db.get("a")
        assert stored is not None and stored.payload is None
        assert temp_db_path.read_text(encoding="utf-8") == contents_before

    def test_failed_delete_keeps_items(self, keyed_db, temp_db_path):
        """A delete whose save fails restores the items it removed."""
        # Stored items are handed out by reference, so this poisons the database
        keyed_db.all()[0].payload = object()
        contents_before = temp_db_path.read_text(encoding="utf-8")

        with pytest.raises(JsonDBException):
            keyed_db.delete(id="b")

        assert [item.id for item in keyed_db.all()] == ["a", "b"]
        assert temp_db_path.read_text(encoding="utf-8") == contents_before

    def test_failed_remove_keeps_item_and_index(self, keyed_db, temp_db_path):
        """A remove whose save fails restores both the item and its index entry."""
        keyed_db.all()[0].payload = object()
        contents_before = temp_db_path.read_text(encoding="utf-8")

        with pytest.raises(JsonDBException):
            keyed_db.remove("b")

        assert [item.id for item in keyed_db.all()] == ["a", "b"]
        restored = keyed_db.get("b")
        assert restored is not None and restored.id == "b"
        assert temp_db_path.read_text(encoding="utf-8") == contents_before
