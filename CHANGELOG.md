# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-01-10

### Added
- Initial public release
- MIT License for open-source distribution
- Python package setup for pip installation
- MCP (Model Context Protocol) server integration
- Backend log search tools (`dd_search_logs`, `dd_trace_logs`, `dd_fetch_log`, `dd_top_values`)
- RUM (Real User Monitoring) tools (`dd_rum_sessions`, `dd_rum_actions`, `dd_rum_errors`, `dd_rum_resources`)
- Authentication via browser session tokens
- JSON/NDJSON output formats
- Profile-based column customization
- Watchdog AI insights integration
- Saved views support

### Removed
- Broken field discovery tools (`dd_fields_search`, `dd_fields_values`) due to Datadog API changes
  - Workaround: Use `dd_top_values` for field exploration

### Security
- Auth tokens stored in `~/.datadog-auth` with 0600 permissions
- Tokens are browser session-based and require manual refresh when expired

### Documentation
- Comprehensive README with installation and usage examples
- Architecture documentation
- MCP server configuration examples
- Security best practices
