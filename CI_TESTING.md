# CI/CD Test Workflows

This repository includes several GitHub Actions workflows for automated testing and quality assurance.

## 🧪 Test Workflows

### 1. `ci-tests.yaml` - Main Test Suite
**Triggers:** Push to `main`, `develop`, `IFDCPB-*` branches, and all PRs
- Runs full test suite with coverage reporting
- Integration tests with PostgreSQL
- Security scanning with Bandit
- Uploads coverage to Codecov

### 2. `multi-rag-tests.yaml` - MultiRagService Tests
**Triggers:** Changes to MultiRagService files
- Focused unit tests for MultiRagService
- Coverage reporting (80% minimum)
- PR comments with test results
- Targeted testing for critical service components

### 3. `ci-dev.yaml` - Development CI
**Triggers:** Push to `main` branch
- Runs tests before deployment
- Generates test report in Markdown format
- Integrated with Docker build process

### 4. `test-badge.yaml` - Status Badge
**Triggers:** Push/PR to `main` branch
- Creates dynamic test status badge
- Updates README with current test status

## 📊 Test Coverage

The test suite includes:
- ✅ **Unit Tests**: Individual component testing
- ✅ **Integration Tests**: Database connectivity and service integration
- ✅ **Security Scans**: Automated vulnerability detection
- ✅ **Coverage Reports**: Detailed code coverage analysis

## 🔧 Local Testing

Run tests locally using:

```bash
# Install dependencies
uv sync --dev

# Run all tests
uv run pytest tests/ -v

# Run specific MultiRagService tests
uv run pytest tests/services/rag_services/services/test_multi_rag_service.py -v

# Run with coverage (Option 1 - Direct)
uv run pytest tests/ --cov=src --cov-report=html

# Run with coverage (Option 2 - Separate - Recommended for complex projects)
uv run coverage run -m pytest tests/ -v
uv run coverage report --show-missing
uv run coverage html
```

## 📈 Test Status

[![Tests](https://img.shields.io/github/actions/workflow/status/infodation/ifd-cpb-python-ai/ci-tests.yaml?branch=main&label=Tests)](https://github.com/infodation/ifd-cpb-python-ai/actions/workflows/ci-tests.yaml)
[![MultiRagService Tests](https://img.shields.io/github/actions/workflow/status/infodation/ifd-cpb-python-ai/multi-rag-tests.yaml?branch=main&label=MultiRagService)](https://github.com/infodation/ifd-cpb-python-ai/actions/workflows/multi-rag-tests.yaml)

---

## 🚀 Quick Start for Contributors

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b IFDCPB-XXX-feature-name`
3. **Make your changes**
4. **Run tests locally**: `uv run pytest`
5. **Push and create PR** - CI will automatically run tests
6. **Wait for green checks** ✅ before merging

All tests must pass before code can be merged to `main`.
