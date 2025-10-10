# Typed JSON DB

[![codecov](https://codecov.io/gh/frangiz/typed-json-db/branch/main/graph/badge.svg?token=7W6IH9PXQO)](https://codecov.io/gh/frangiz/typed-json-db)

A lightweight, type-safe JSON-based database for Python applications using dataclasses. Choose between two database types based on your needs:

- **`JsonDB`** - Simple storage with basic operations (add, find, all)
- **`IndexedJsonDB`** - Advanced storage with primary key support (get, update, remove) and indexing

## Features

- 🚀 **Type-safe** with full generic type support
- 📁 **File-based** JSON storage - easy to inspect and backup  
- 🔍 **Query support** using attribute-based queries
- � **Two database types** for different use cases
- ⚡ **Fast lookups** with automatic primary key indexing
- 📦 **Zero dependencies** required
- 🆔 **UUID support** and nested dataclasses

## Installation

```bash
pip install typed-json-db
```

## Quick Start

```python
from dataclasses import dataclass
from enum import Enum
import uuid
from pathlib import Path
from typed_json_db import JsonDB, IndexedJsonDB

@dataclass
class User:
    id: uuid.UUID
    name: str
    email: str
    status: str
    age: int

# Simple database - basic operations only
simple_db = JsonDB(User, Path("users.json"))
simple_db.add(user)
users = simple_db.find(status="active")
all_users = simple_db.all()

# Indexed database - full CRUD with fast lookups
indexed_db: IndexedJsonDB[User, uuid.UUID] = IndexedJsonDB(
    User, Path("users.json"), primary_key="id"
)
indexed_db.add(user)
user = indexed_db.get(user_id)        # Fast O(1) lookup
indexed_db.update(modified_user)      # Update by primary key
indexed_db.remove(user_id)            # Remove by primary key
```

## Database Types

### JsonDB - Simple Storage

Use `JsonDB` when you need basic storage without primary key constraints:

```python
db = JsonDB(User, Path("users.json"))

# Available operations
db.add(item)                   # Add new items
db.find(field=value)           # Query by any field  
db.all()                       # Get all items
db.save()                      # Manual save (auto-saves on add)
```

### IndexedJsonDB - Advanced Storage  

Use `IndexedJsonDB` when you need primary key support and fast lookups:

```python
db: IndexedJsonDB[User, uuid.UUID] = IndexedJsonDB(
    User, Path("users.json"), primary_key="id"
)

# All JsonDB operations plus:
db.get(primary_key)            # Fast O(1) primary key lookup
db.update(item)                # Update existing item by primary key
db.remove(primary_key)         # Remove by primary key
db.find(id=primary_key)        # Optimized primary key search
```

**Key Benefits:**
- ⚡ **Fast lookups** - O(1) primary key operations via automatic indexing
- 🔒 **Uniqueness enforcement** - Primary key values must be unique
- 🎯 **Type safety** - Generic types for both data and primary key
- 🔄 **Auto-indexing** - Index maintained automatically on all operations

## API Reference

### Common Methods (Both Classes)

```python
db.add(item: T) -> T                    # Add new item, auto-saves
db.find(**kwargs) -> List[T]            # Query by any field  
db.all() -> List[T]                     # Get all items
db.save() -> None                       # Manual save
```

### IndexedJsonDB Additional Methods

```python
db.get(key: PK) -> Optional[T]          # Fast O(1) lookup by primary key
db.update(item: T) -> T                 # Update by primary key, auto-saves  
db.remove(key: PK) -> bool              # Remove by primary key, auto-saves
```

## Examples

### Type Safety with UUIDs

```python
import uuid
from dataclasses import dataclass

@dataclass
class User:
    id: uuid.UUID
    name: str
    email: str

# Type-safe primary key operations  
db: IndexedJsonDB[User, uuid.UUID] = IndexedJsonDB(User, Path("users.json"), primary_key="id")

user_id = uuid.uuid4()
db.add(User(id=user_id, name="Alice", email="alice@example.com"))

# IDE provides type checking and autocomplete
user = db.get(user_id)  # ✅ Expects UUID
# user = db.get("string")  # ❌ Type error
```

### Automatic Type Conversion

Supports automatic serialization of:
- UUID, datetime, date objects
- Enums and nested dataclasses  
- Lists of dataclasses

```python
from datetime import datetime
from enum import Enum

class Status(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"

@dataclass  
class Order:
    id: uuid.UUID
    created_at: datetime
    status: Status
    items: List[Product]  # Nested dataclasses

# All types automatically converted to/from JSON
db: IndexedJsonDB[Order, uuid.UUID] = IndexedJsonDB(Order, Path("orders.json"), primary_key="id")
```

### Performance

- **IndexedJsonDB**: O(1) primary key operations via automatic indexing
- **JsonDB**: O(n) linear search for all operations
- **Auto-indexing**: Index maintained automatically on all operations
- **Memory efficient**: Index rebuilt on database load

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
