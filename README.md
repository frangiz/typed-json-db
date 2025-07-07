# Simple JSON DB

A lightweight, type-safe JSON-based database for Python applications using dataclasses. Perfect for small projects, prototyping, and situations where you need a simple persistent storage solution with type safety.

## Features

- 🚀 **Type-safe**: Uses Python dataclasses for structured data
- 📁 **File-based**: Uses JSON files for storage - easy to inspect and backup
- 🔍 **Query support**: Find records using attribute-based queries
- 🔧 **CRUD operations**: Create, Read, Update, Delete operations
- 📦 **Zero dependencies**: No external dependencies required
- 🐍 **Type hints**: Full type hint support with generics
- ✅ **Well tested**: Comprehensive test suite
- 🆔 **UUID support**: Automatic handling of UUID fields

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

### JsonDB[T](data_class: Type[T], file_path: Path)

Create a new type-safe database instance.

**Parameters:**
- `data_class`: The dataclass type this database will store
- `file_path`: Path to the JSON database file

### Methods

#### add(item: T) -> T
Add a new item to the database and save automatically.

#### get(id_value: uuid.UUID) -> Optional[T]
Get an item by its UUID. Returns None if not found.

#### find(**kwargs) -> List[T]
Find all items matching the given attribute criteria.

#### all() -> List[T]
Get all items in the database.

#### update(item: T) -> T
Update an existing item (by ID) and save automatically.

#### remove(id_value: uuid.UUID) -> bool
Remove an item by its UUID. Returns True if removed, False if not found.

#### save() -> None
Manually save the database (automatic for add/update/remove operations).

## Advanced Features

### Automatic Type Conversion

The database automatically handles serialization/deserialization of:
- UUID fields
- Enum values  
- datetime and date objects
- Complex nested dataclass structures

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