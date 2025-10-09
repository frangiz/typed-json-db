# Simple JSON DB

[![codecov](https://codecov.io/gh/frangiz/typed-json-db/branch/main/graph/badge.svg?token=7W6IH9PXQO)](https://codecov.io/gh/frangiz/typed-json-db)

A lightweight, type-safe JSON-based database for Python applications using dataclasses. Perfect for small projects, prototyping, and situations where you need a simple persistent storage solution with full type safety.

## Features

- 🚀 **Type-safe**: Uses Python dataclasses for structured data with full generic type support
- 📁 **File-based**: Uses JSON files for storage - easy to inspect and backup
- 🔍 **Query support**: Find records using attribute-based queries
- 🔧 **CRUD operations**: Create, Read, Update, Delete operations
- 🔑 **Primary key support**: Optional configurable primary key with uniqueness enforcement and type safety
- ⚡ **Indexing**: Automatic indexing for primary key operations for fast lookups
- 📦 **Zero dependencies**: No external dependencies required
- 🐍 **Advanced type hints**: Full type hint support with generics including primary key types
- ✅ **Well tested**: Comprehensive test suite
- 🆔 **UUID support**: Automatic handling of UUID fields
- 🔄 **Nested dataclasses**: Supports lists of dataclasses and complex nested structures

## Installation

Install from PyPI using pip:

```bash
pip install typed-json-db
```

Or using uv:

```bash
uv add typed-json-db
```

## Quick Start

```python
from dataclasses import dataclass
from enum import Enum
import uuid
from pathlib import Path
from typed_json_db import JsonDB

# Define your data structure using dataclasses
class Status(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"

@dataclass
class User:
    id: uuid.UUID
    name: str
    email: str
    status: Status
    age: int

# Create or connect to a database
db = JsonDB(User, Path("users.json"))

# Or create with a primary key for better performance and uniqueness enforcement
# Note: JsonDB is generic over both data type and primary key type for better type safety
db: JsonDB[User, uuid.UUID] = JsonDB(User, Path("users.json"), primary_key="id")

# Add records
user1 = User(
    id=uuid.uuid4(),
    name="Alice Johnson", 
    email="alice@example.com",
    status=Status.ACTIVE,
    age=30
)
db.add(user1)

# Find records
active_users = db.find(status=Status.ACTIVE)
specific_user = db.get(user1.id)
all_users = db.all()

# Update records (modify and save)
user1.age = 31
db.update(user1)

# Remove records
db.remove(user1.id)
```

## API Reference

### JsonDB[T, PK](data_class: Type[T], file_path: Path, primary_key: Optional[str] = None)

Create a new type-safe database instance.

**Type Parameters:**
- `T`: The dataclass type this database will store
- `PK`: The type of the primary key field (e.g., `str`, `int`, `uuid.UUID`)

**Parameters:**
- `data_class`: The dataclass type this database will store
- `file_path`: Path to the JSON database file
- `primary_key`: Optional field name to use as primary key for uniqueness and indexing

**Example:**
```python
# Database with UUID primary key
db: JsonDB[User, uuid.UUID] = JsonDB(User, Path("users.json"), primary_key="id")

# Database with string primary key  
db: JsonDB[Product, str] = JsonDB(Product, Path("products.json"), primary_key="sku")

# Database without primary key
db: JsonDB[LogEntry, Any] = JsonDB(LogEntry, Path("logs.json"))
```

### Methods

#### add(item: T) -> T
Add a new item to the database and save automatically. If a primary key is configured, enforces uniqueness.

#### get(primary_key_value: PK) -> Optional[T]
Get an item by its primary key value. Returns None if not found. Requires a primary key to be configured.

**Type Safety**: When using typed primary keys, IDEs will provide autocomplete and type checking for the key parameter.

#### find(**kwargs) -> List[T]
Find all items matching the given attribute criteria. Requires at least one search criterion.

#### all() -> List[T]
Get all items in the database.

#### update(item: T) -> T
Update an existing item (by primary key) and save automatically. Requires a primary key to be configured.

#### remove(primary_key_value: PK) -> bool
Remove an item by its primary key value. Returns True if removed, False if not found. Requires a primary key to be configured.

#### save() -> None
Manually save the database (automatic for add/update/remove operations).

## Advanced Features

### Primary Key Configuration

Configure a primary key for better performance and data integrity:

```python
@dataclass
class Product:
    sku: str
    name: str
    price: float

# Use 'sku' as primary key with proper typing
db: JsonDB[Product, str] = JsonDB(Product, Path("products.json"), primary_key="sku")

# Primary key operations are fast (O(1)) and enforce uniqueness
product = Product(sku="ABC123", name="Widget", price=9.99)
db.add(product)

# Fast retrieval by primary key - IDE knows key should be a string
found = db.get("ABC123")  # Type-safe: expects str

# Trying to add duplicate primary key raises an exception
duplicate = Product(sku="ABC123", name="Another Widget", price=19.99)
# db.add(duplicate)  # Raises JsonDBException
```

### Advanced Type Safety Examples

The database supports full type safety including primary key types:

```python
import uuid
from dataclasses import dataclass
from typing import List

@dataclass 
class Address:
    street: str
    city: str
    zip_code: str

@dataclass
class User:
    id: uuid.UUID
    name: str
    addresses: List[Address]  # Nested dataclasses are supported
    age: int

# Full type safety with UUID primary key
db: JsonDB[User, uuid.UUID] = JsonDB(User, Path("users.json"), primary_key="id")

user_id = uuid.uuid4()
user = User(
    id=user_id,
    name="Alice",
    addresses=[Address("123 Main St", "Anytown", "12345")],
    age=30
)

db.add(user)

# Type-safe retrieval - IDE knows this expects UUID
found_user = db.get(user_id)  # ✅ Correct type
# found_user = db.get("string")  # ❌ Type checker will warn
```

### Database Operations Without Primary Key

You can still use the database without a primary key, but some operations will be limited:

```python
# No primary key specified
db = JsonDB(User, Path("users.json"))

# These work normally
db.add(user)
users = db.find(status=Status.ACTIVE)
all_users = db.all()

# These require a primary key and will raise JsonDBException
# db.get(some_id)      # Not available
# db.update(user)      # Not available  
# db.remove(some_id)   # Not available
```

### Automatic Type Conversion

The database automatically handles serialization/deserialization of:
- UUID fields
- Enum values  
- datetime and date objects
- Complex nested dataclass structures
- Lists of dataclasses

```python
@dataclass
class Order:
    id: uuid.UUID
    items: List[Product]  # List of dataclasses
    created_at: datetime
    status: Status  # Enum

# All types are automatically serialized to/from JSON
db: JsonDB[Order, uuid.UUID] = JsonDB(Order, Path("orders.json"), primary_key="id")
```

### Performance and Indexing

When a primary key is configured, the database automatically creates an in-memory index for fast lookups:

- **Primary key operations** (`get`, single-key `find`) are O(1) - constant time
- **Non-primary key searches** use linear search - O(n) time
- **Index is automatically maintained** during add, update, and remove operations
- **Index is rebuilt** when loading the database from disk

```python
# Fast O(1) operations with primary key
db: JsonDB[User, uuid.UUID] = JsonDB(User, Path("users.json"), primary_key="id")
user = db.get(user_id)  # Very fast, uses index, type-safe

# Linear search operations (still fast for reasonable dataset sizes)
active_users = db.find(status=Status.ACTIVE)  # Searches all records
```

### Error Handling

```python
from typed_json_db import JsonDBException

try:
    db.add(invalid_item)
except JsonDBException as e:
    print(f"Database error: {e}")
```

## Development

This project uses `uv` for dependency management and packaging.

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/frangiz/typed-json-db.git
cd typed-json-db

# Install development dependencies
uv sync
```

### Running Tests

```bash
make test
```

### Code Formatting and Checking

```bash
make format
make check
```

### Building the Package

```bash
make build
```

### Publishing to PyPI

```bash
# Test on TestPyPI first
make publish-test

# Publish to PyPI
make publish
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
