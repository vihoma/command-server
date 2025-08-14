# Command Server Agent Guide

## Build & Test Commands
- Install dependencies: `poetry install`
- Run server: `poetry run python -m command_server`
- Run client: `poetry run python -m command_client`
- Run all tests: `poetry run pytest`
- Run single test: `poetry run pytest -k "test_name"`

## Code Style Guidelines
### General
- Follow PEP 8 conventions
- Use snake_case for variables/functions
- Use PascalCase for classes
- Use absolute imports

### Formatting
- Max line length: 88 characters
- Use f-strings for string formatting
- Use double quotes for strings

### Error Handling
- Catch specific exceptions
- Use custom exception classes for domain errors
- Log errors with context using rich

### Types
- Use type hints for all function signatures
- Use Optional for nullable return values
- Use Union for multiple possible types

### Documentation
- Use Google-style docstrings
- Include type information in docstrings
- Document public interfaces only