# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- A save that cannot be serialized no longer corrupts the database file. Serialization now completes in memory before the file is opened, so an item the serializer cannot encode leaves the previous contents intact and readable instead of truncating the file mid-write. Circular and self-referential values now also raise `JsonDBException` rather than propagating a `ValueError` or `RecursionError`.
- A save that cannot be serialized no longer leaves the in-memory data out of step with the file. `add()`, `update()`, `delete()` and `remove()` now roll back their change when serialization fails, so the database stays usable instead of raising on every later save, and `IndexedJsonDB` no longer keeps a key in its items while missing it from the primary key index — which allowed a duplicate primary key to be added and persisted. I/O errors while writing are unaffected and still propagate without a rollback.

## [0.4.0] - 2026-06-26

### Added
- New `delete(**kwargs)` method on `JsonDB` for query-based deletion, returning the number of items removed. `IndexedJsonDB` overrides it to keep the primary key index in sync.
- New `count(**kwargs)` method on `JsonDB` returning the number of items, optionally filtered by criteria.
- Pythonic protocol support on `JsonDB`: `len(db)`, iteration (`for item in db`), and membership testing (`item in db`).

## [0.3.1] - 2025-11-24

### Added
- New `Timestamped` base class for automatic timestamp management
- Automatic `created_at` and `updated_at` timestamp setting on `add()` operations
- Automatic `updated_at` timestamp refresh on `update()` operations

### Fixed
- Enhanced JSON deserialization to properly handle `Optional` type fields (e.g., `Optional[datetime]`)

## [0.3.0] - 2025-10-10

### Added
- New `IndexedJsonDB` class for advanced database operations with primary key support
- Automatic indexing for O(1) primary key lookups in `IndexedJsonDB`
- Enhanced type safety with separate classes for different use cases

### Changed
- **BREAKING**: Refactored class structure - `JsonDB` is now simple storage without primary key methods
- **BREAKING**: Primary key support moved to new `IndexedJsonDB` class
- **BREAKING**: `IndexedJsonDB` requires primary key parameter (no longer optional)
- Improved API design with clearer separation of concerns
- Updated documentation to better highlight the two database types
- Streamlined README for better readability and clarity

### Removed
- **BREAKING**: Removed `get()`, `update()`, and `remove()` methods from base `JsonDB` class
- **BREAKING**: Removed optional primary key parameter from base `JsonDB` class

### Migration Guide
- For basic storage without primary keys: Continue using `JsonDB(DataClass, path)`
- For advanced operations with primary keys: Use `IndexedJsonDB(DataClass, path, primary_key="field")`
- Update imports to include `IndexedJsonDB` if you need primary key functionality

## [0.2.3] - 2025-XX-XX

### Added
- Comprehensive test suite
- Type safety improvements
- Support for nested dataclasses and complex types

### Fixed
- Various bug fixes and stability improvements

### Changed
- Improved error messages and exception handling

## [0.2.2] - 2025-XX-XX

### Added
- Enhanced UUID support
- Better serialization for datetime objects
- Support for Enum types

## [0.2.1] - 2025-XX-XX

### Fixed
- Serialization issues with complex types
- File handling improvements

## [0.2.0] - 2025-XX-XX

### Added
- Generic type support
- Primary key functionality
- Advanced type hints

### Changed
- Improved performance for large datasets

## [0.1.0] - 2025-XX-XX

### Added
- Initial release
- Basic JSON database functionality
- Dataclass integration
- File-based storage