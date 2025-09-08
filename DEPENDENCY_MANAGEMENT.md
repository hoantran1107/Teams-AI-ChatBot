# Dependency Management Strategy

## Problem Solved

Before adding pytest and testing dependencies, both main/dev and prod/release branches used the same `uv.lock` file. After adding testing dependencies to the dev group, production deployments would unnecessarily include testing packages.

## Solution Implemented

### 1. Dependency Groups Structure

```toml
# pyproject.toml
[project]
dependencies = [
    # Production runtime dependencies only
    "fastapi", "uvicorn", "sqlalchemy", ...
]

[project.optional-dependencies]  
dev = ["pytest", "pytest-asyncio", "pytest-md-report"]

[dependency-groups]
dev = [
    # Additional dev-only dependencies
    "factory-boy>=3.3.3",
    "pytest-cov>=6.2.1", 
    "pytest-mock>=3.14.1",
    "pytest-xdist>=3.8.0",
]
```

### 2. Docker Configuration

#### Production Docker (`Dockerfile`)
```dockerfile
# Excludes dev dependencies - production ready
RUN uv pip install --system . --no-group dev
```

#### Development Docker (`Dockerfile.debug`)  
```dockerfile
# Includes dev dependencies for testing/debugging
RUN uv pip install --system . debugpy --with dev
```

### 3. Local Development Commands

```bash
# Production dependencies only
uv sync

# Development dependencies (includes testing tools)
uv sync --dev
```

### 4. CI/CD Behavior

- **Production pipelines** (`ci-main.yaml`): Use `Dockerfile` → no test dependencies
- **Development pipelines** (`ci-dev.yaml`): Use `Dockerfile` → no test dependencies  
- **Local development**: Use `uv sync --dev` → includes test dependencies

## Benefits

✅ **Production builds are lean** - no testing dependencies in deployed containers
✅ **Single uv.lock file** - simplified dependency management  
✅ **Flexible development** - devs can choose production or dev dependencies locally
✅ **CI consistency** - production builds identical between dev and main branches
✅ **Docker layer optimization** - production images smaller and faster

## Usage Examples

```bash
# Development workflow
uv sync --dev                    # Install with testing tools
pytest --cov=src -v             # Run tests with coverage

# Production simulation  
uv sync                          # Install production deps only
python main.py                   # Run as production would

# Docker development
docker build -f Dockerfile.debug -t app-dev .     # With dev dependencies
docker build -f Dockerfile -t app-prod .          # Production ready
```

## Migration Notes

- Existing `uv.lock` remains unchanged
- No changes needed for existing CI/CD workflows  
- Developers should use `uv sync --dev` for local development going forward
- Production deployments automatically exclude testing dependencies
