# Contributing to datadog-log-inspect

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Development Setup

### Prerequisites
- Python 3.9 or higher
- Node.js 18 or higher (for MCP server)
- Git

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/datadog-log-inspect.git
cd datadog-log-inspect
```

2. **Install Python dependencies**
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"
```

3. **Install MCP server dependencies**
```bash
cd mcp
npm install
npm run build
```

## Development Workflow

### Making Changes

1. Create a feature branch: `git checkout -b feature/my-feature`
2. Make your changes
3. Run tests: `pytest tests/`
4. Run linting: `ruff check dd_cli/`
5. Format code: `black dd_cli/`
6. Commit with descriptive message
7. Push and create pull request

### Code Style

- **Python**: Follow PEP 8, enforced by `ruff` and `black`
- **TypeScript**: Follow project's TSConfig settings
- **Commits**: Use conventional commits format (e.g., `feat:`, `fix:`, `docs:`)

### Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=dd_cli --cov-report=html

# Run specific test file
pytest tests/test_client.py -v
```

### Building MCP Server

```bash
cd mcp
npm run build

# Test with MCP inspector
npm run inspector
```

## Adding New Features

### Adding a New CLI Command

1. **Add method to `DatadogWebLogs`** in `dd_cli/client.py`:
```python
def my_new_feature(self, query: str, hours: int = 24) -> List[Dict]:
    """Fetch data using new API endpoint."""
    # Implementation
```

2. **Add CLI subcommand** in `dd_cli/cli.py`:
```python
def cmd_my_feature(args):
    """Handler for new command."""
    client = require_auth()
    results = client.my_new_feature(args.query, args.hours)
    for result in results:
        emit_json(result)
```

3. **Add argument parser**:
```python
parser_my = subparsers.add_parser('my-feature', help='My new feature')
parser_my.add_argument('query', help='Query string')
parser_my.set_defaults(func=cmd_my_feature)
```

### Adding MCP Tool

Add to `mcp/src/tools/index.ts`:
```typescript
{
  name: "dd_my_feature",
  description: "Description of what it does",
  inputSchema: {
    type: "object",
    properties: {
      query: { type: "string", description: "Query string" },
    },
    required: ["query"],
  },
}
```

Update handler in same file.

## Pull Request Process

1. **Update documentation**: README, ARCHITECTURE, or CHANGELOG as needed
2. **Add tests**: All new features should have tests
3. **Update CHANGELOG**: Add entry under "Unreleased" section
4. **Ensure CI passes**: All tests and linting must pass
5. **Get review**: At least one maintainer approval required

### PR Title Format
- `feat: Add new feature`
- `fix: Fix bug description`
- `docs: Update documentation`
- `refactor: Code refactoring`
- `test: Add tests`

## Reporting Issues

### Bug Reports

Include:
- Datadog-log-inspect version (`dd-cli --version` or check `dd_cli/__init__.py`)
- Python version (`python --version`)
- Operating system
- Steps to reproduce
- Error messages/logs
- Expected vs actual behavior

### Feature Requests

Include:
- Use case description
- Proposed API/interface
- Any relevant Datadog API endpoints or documentation

## Code Review Guidelines

Reviewers should check:
- [ ] Code follows style guidelines
- [ ] Tests are included and passing
- [ ] Documentation is updated
- [ ] No secrets or tokens in code
- [ ] Error handling is appropriate
- [ ] Performance impact considered

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Questions?

Open an issue for discussion or reach out to maintainers.
