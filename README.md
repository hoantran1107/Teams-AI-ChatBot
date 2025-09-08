# IFD-CPB-Python-AI

[![Python](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)
[![Pylint](https://img.shields.io/badge/pylint-green.svg)](https://pylint.pycqa.org/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![deploy-prod](https://github.com/infodation/ifd-cpb-python-ai/actions/workflows/ci-prod.yaml/badge.svg)](https://github.com/infodation/ifd-cpb-python-ai/actions/workflows/ci-prod.yaml)
[![deploy-dev](https://github.com/infodation/ifd-cpb-python-ai/actions/workflows/ci-dev.yaml/badge.svg)](https://github.com/infodation/ifd-cpb-python-ai/actions/workflows/ci-dev.yaml)
[![docling-module](https://github.com/infodation/ifd-cpb-python-ai/actions/workflows/ci-docling.yaml/badge.svg)](https://github.com/infodation/ifd-cpb-python-ai/actions/workflows/ci-docling.yaml)
[![Quality Gate Status](https://sonarqube.infodation.com/api/project_badges/measure?project=infodation_ifd-cpb-python-ai_a72a641c-5c37-4147-a253-be4621209bc3&metric=alert_status&token=sqb_a825a982a67d14b705126506846cb0aa28f907d5)](https://sonarqube.infodation.com/dashboard?id=infodation_ifd-cpb-python-ai_a72a641c-5c37-4147-a253-be4621209bc3)
[![Coverage](https://sonarqube.infodation.com/api/project_badges/measure?project=infodation_ifd-cpb-python-ai_a72a641c-5c37-4147-a253-be4621209bc3&metric=coverage&token=sqb_a825a982a67d14b705126506846cb0aa28f907d5)](https://sonarqube.infodation.com/dashboard?id=infodation_ifd-cpb-python-ai_a72a641c-5c37-4147-a253-be4621209bc3)
[![Lines of Code](https://sonarqube.infodation.com/api/project_badges/measure?project=infodation_ifd-cpb-python-ai_a72a641c-5c37-4147-a253-be4621209bc3&metric=ncloc&token=sqb_a825a982a67d14b705126506846cb0aa28f907d5)](https://sonarqube.infodation.com/dashboard?id=infodation_ifd-cpb-python-ai_a72a641c-5c37-4147-a253-be4621209bc3)
[![Duplicated Lines (%)](https://sonarqube.infodation.com/api/project_badges/measure?project=infodation_ifd-cpb-python-ai_a72a641c-5c37-4147-a253-be4621209bc3&metric=duplicated_lines_density&token=sqb_a825a982a67d14b705126506846cb0aa28f907d5)](https://sonarqube.infodation.com/dashboard?id=infodation_ifd-cpb-python-ai_a72a641c-5c37-4147-a253-be4621209bc3)
[![.github/workflows/ci-garak.yaml](https://github.com/infodation/ifd-cpb-python-ai/actions/workflows/ci-garak.yaml/badge.svg)](https://github.com/infodation/ifd-cpb-python-ai/actions/workflows/ci-garak.yaml)

A **FastAPI application** designed for seamless **AI-Teams app integration projects**.

**Reference**: [IFDINTS-377](https://infodation.atlassian.net/browse/IFDINTS-377)

---

## Prerequisites

Before getting started, ensure you have the following installed:

- **Python**: Version 3.13 or higher

- **pip**: Python package manager (comes pre-installed with Python 3.4+)

- **PostgreSQL**: For vector database storage

- **Docker**: (Optional) For containerized deployment

## Project-specific tools

- **uv**: <https://docs.astral.sh/uv/getting-started/installation/#winget>

- **Ruff**: <https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff>

- **git flow**: built-in with git
- **Teams Toolkit/Microsoft 365 Agents Toolkit**: <https://marketplace.visualstudio.com/items?itemName=TeamsDevApp.ms-teams-vscode-extension>

---

## Setup Instructions

Follow the steps below to install and run the application:

### 1. Clone the Repository

Use the following command to clone this repository:

```bash

git  clone  https://github.com/infodation/ifd-cpb-python-ai.git

cd  ifd-cpb-python-ai

```

Or using GitHub Desktop or any similar tools

### 2. Create a Virtual Environment & Install Requirements

Python virtual environments are recommended to isolate dependencies.

#### Windows

First, run `uv init` if the project is not already initialized
Then, in terminal opened in project folder ie. `PS D:\repos\ifd-cpb-python-ai>`:

```bash
uv venv
.venv\Scripts\activate
uv sync
uv sync --extra dev
```

To create, activate virtual environment and install requirements
(`uv sync` will install dependencies from `pyproject.toml`)
(`uv sync --extra dev` will install dependencies from `pyproject.toml` and `dev` group for running tests)

#### Production vs Development Dependencies

This project uses **dependency groups** to separate production and development dependencies:

- **Production**: Only essential runtime dependencies
- **Development**: Includes testing tools, debugging, and development utilities

**Key Commands:**
```bash
# Production installation (CI/Docker)
uv sync                          # Production dependencies only

# Development installation (local work)  
uv sync --dev                    # Production + development dependencies
```

**Docker Behavior:**
- `Dockerfile` (production): Uses `--no-group dev` to exclude testing dependencies
- `Dockerfile.debug` (development): Uses `--with dev` to include all dependencies

#### Development Dependencies Installed with `--extra dev`:
- **pytest** - Testing framework
- **pytest-cov** - Coverage reporting  
- **pytest-mock** - Advanced mocking
- **pytest-xdist** - Parallel test execution
- **factory-boy** - Test data generation
- **Other dev tools** - Linting, formatting, and debugging tools

### 3. Install New Dependencies

Install new Python packages using `uv add` , for example:

```bash

uv add uv uvicorn webcolors

```

  It will automatically update pyproject.toml, using requirement.txt should be unnecessary.

### 4. Environment Variables

Create a `.env` file in the project root. Add the necessary configuration variables (refer to the **IFD Copilot Bot 1Password vault** for credentials or check the `.env.example` file if available).

### 5. Quick Development Commands

```bash
# Development workflow
uv sync --extra dev              # Install all dependencies including dev tools
python main.py                   # Run the application
pytest tests/ -v                         # Run tests without coverage
uv run coverage run -m pytest tests/ -v    # Run tests with coverage collection  
uv run coverage report --show-missing      # Generate terminal coverage report

# Testing commands
pytest tests/services/ tests/bots/handlers/test_rag_process_minimal.py -v    # Run working tests
uv run coverage html                        # Generate HTML coverage report
uv run coverage run -m pytest tests/ -v    # Run tests with coverage
uv run coverage xml                         # Generate XML coverage for CI
pytest -n 2 tests/                                                           # Run tests in parallel

# Package management
uv add package-name              # Add new package
uv add --dev pytest-new-plugin  # Add development dependency
uv tree                         # Show dependency tree
```

---

## Working with Git Flow

Refer to: [https://www.geeksforgeeks.org/git-flow/](https://www.geeksforgeeks.org/git-flow/)

### Initializing Git Flow in a Repository

**Step 1: Navigate to Your Repository**

Open your terminal and navigate to the root of your Git repository.

**Step 2: Initialize Git Flow**

    git flow init

This command will prompt you to set up the main and develop branches, and configure prefixes for feature, release, and hotfix branches.

### Creating and Merging Feature Branches

**Step 1: Create a Feature Branch:**

git flow feature start <feature-name>
This command creates a new branch from develop named feature/<feature-name>.

**Step 2: Develop Your Feature**

Commit your changes as you work on the feature.

**Step 3: Finish the Feature:**

    git flow feature finish <feature-name>

This merges the feature branch back into develop and deletes the feature branch.

### Creating Release Branches

**Step 1: Start a Release Branch:**

    git flow release start <version>

This command creates a release branch from develop.

**Step 2: Prepare the Release**

Make any final changes, such as version bumping and documentation updates.

**Finish the Release:**

    git flow release finish <version>

This merges the release branch into both main and develop, tags the commit on main, and deletes the release branch.

---

## Continuous Integration (CI/CD)

The project uses GitHub Actions for automated building, testing, and deployment across multiple environments.

### CI/CD Workflows

#### Production Pipeline (`ci-main.yaml`)
- **Trigger**: Pushes to `release*` branches
- **Actions**: 
  - Version tagging
  - Docker image building and pushing to GCP Artifact Registry
  - Cloud Run deployment for main service and document handler
  - GitHub release creation

#### Development Pipeline (`ci-dev.yaml`)  
- **Trigger**: Pushes to `main` branch
- **Actions**:
  - Development environment deployment
  - Docker image building for development testing
  - *Note*: Testing is currently commented out but can be enabled

#### Specialized Pipelines
- **`ci-docling.yaml`**: Document processing service CI
- **`ci-garak.yaml`**: Security testing with Garak framework
- **`build.yml`**: General build pipeline

### Enabling Tests in CI

To enable automated testing in the CI pipeline, uncomment the test section in `.github/workflows/ci-dev.yaml`:

```yaml
- name: Run Tests
  run: |
    uv sync --extra dev
    pytest --cov=src --cov-report=term-missing tests/services/ tests/bots/handlers/test_rag_process_minimal.py

- name: Upload Coverage Reports
  uses: codecov/codecov-action@v3
  if: always()
  with:
    file: ./coverage.xml
```

### Environment Configuration

All workflows use:
- **Python 3.13**
- **UV package manager** for dependency management
- **Google Cloud Platform** for container registry and deployment
- **Self-hosted runners** for consistent environment

### Deployment Targets

- **Production**: Cloud Run services in `asia-southeast1` region
- **Development**: Separate dev environment for testing
- **Artifact Storage**: GCP Artifact Registry at `asia-southeast1-docker.pkg.dev`

---

## Running the App locally

Once the setup is complete, the entire Teams app + Python app can be launched either using Teams Toolkit/Microsoft 365 Agents Toolkit:

![image](https://github.com/user-attachments/assets/a1a8a3a3-7b3c-4b70-97a3-9b32f2f36d1a)

Or scripts in `.vscode/launch.json`

![image](https://github.com/user-attachments/assets/a678456e-21e7-45f3-952b-cf78b485dad7)

You can also run python app separately

```bash
python main.py
```

By default, the application runs on `http://127.0.0.1:5000/`. Visit this URL in your web browser to access the app.

---

## Run the App locally (docker)

1.Open Dockerdesktop, then navigate to project's root folder
2. Build docker with:

```bash
docker build -t ifd-cpb-python-ai . 
```

3. Then run it with your custom .env.local file:

```bash
docker run -p 5000:5000 --env-file .env.local ifd-cpb-python-ai 
```

4. Start devtunnel with bot's port:

```bash
devtunnel host -p 5000
```
## Test the app with GCP docker
Go to action and find the url of the GCP artifact and  pull the docker image to your local machine, then run it, for example docker run command:

```bash
docker run -d -p 8000:8000 -v "C:/Users/DuyTuNgo/Downloads/IFD-Cpb.json:/app/credentials/IFD-Cpb.json" -e GOOGLE_APPLICATION_CREDENTIALS=/app/credentials/IFD-Cpb.json -e DB_NAME=rag_sync -e DB_USER=postgres -e DB_HOST=35.186.158.211 -e DB_PORT=5432 sha256:4f36fd338452ee1feca655f690d2e2bd4860677ee9ccfe5710dad95c7737ea74 uv tree -d 1
```

---
## Red teaming (w/ Garak)
Garak includes many red teaming probes. Some common ones include:

- `dan` - "Do Anything Now" jailbreak attempts
- `malwaregen` - Attempts to generate malware code
- `packagehallucination` - Tests for package hallucination
- `encoding` - Encoding-based attacks
- `leakage` - Information leakage tests
- `toxicity` - Toxicity generation tests

Please ensure your bot can serve OpenAI Compatible requests, or other API types that Garak supports.

If not, consider making custom route/adapter for Garak, refer to:
 - src\bots\console_adapter.py
 - src\routes\test_route.py

For examples.

After clone/install garak, make a config file for your test endpoint:


```yaml
plugins:
  generators:
    rest:
      RestGenerator:
        uri: "http://localhost:5000/chat/completions" # Your bot's test endpoint
        method: "post"
        req_template_json_object:
          messages:
            - role: "user"
              content: "$INPUT"
        response_json: true
        response_json_field: "$.choices[0].message.content" # Place to extract message body from response content
        headers:
          Content-Type: "application/json"
        request_timeout: 60  # Increased timeout to 60 seconds
```
Then, run the garak command with it:
```bash
python -m garak --model_type rest --model_name RestGenerator --config ifd_bot_config.yaml --probes dan
```
### Garak troubleshooting
#### Garak Connection Issues
- Check the `uri` in your configuration file
- Verify `request_timeout` is sufficient for your bot's response time
- Check `ratelimit_codes` and `skip_codes` if getting HTTP errors

#### Response Format Issues
- Verify `response_json_field` matches your bot's response structure
- Check that your bot returns valid JSON
- Use simple configuration if OpenAI format is problematic

#### Performance Issues
- Reduce the number of probes for faster testing
- Increase `request_timeout` if bot responses are slow
- Use `--max_attempts` to limit test attempts per probe

### Results

Test results are saved in the `garak_results` directory with:
- HTML reports for easy viewing
- JSON data for programmatic analysis
- Detailed logs of all interactions
---
  
## Core Features

- **RAG Service**: Retrieval-Augmented Generation for knowledge base querying

- Document vector storage in PostgreSQL

- Semantic search for relevant information

- Support for various document types (text, tables, images)

- **LangGraph Integration**: For building complex conversational flows

- Structured processing pipelines for LLM interactions

- Document retrieval and analysis nodes

- Table analysis and processing

- **Azure OpenAI Integration**: Leverages Azure's OpenAI services

- Chat completions

- Embeddings for document vectorization

- Content generation and summarization

- **Document Processing Pipeline**: Handles various document formats

- PDF processing

- Word document processing

- Image and table extraction

- OCR capabilities

- **Confluence Integration**: Connect with Atlassian Confluence for document sources

---

## Project Structure

```tree

ifd-cpb-python-ai/

├── migrations/ # Database migration files for PostgreSQL
│
├── src/ # Core application source code
│ ├── config/ # Configuration files and app initialization
│ ├── constants/ # Constant values used across the project
│ ├── services/ # Implementation of application services
│ │ ├── auto_test/ # Automated testing services
│ │ ├── confluence_service/ # Atlassian Confluence integration
│ │ ├── cronjob/ # Scheduled job services
│ │ ├── custom_llm/ # Custom LLM service implementations
│ │ │ ├── controllers/ # LLM-specific controllers
│ │ │ └── services/ # LLM utilities and services
│ │ ├── google_cloud_services/ # Google Cloud integration
│ │ ├── manage_rag_sources/ # Document source management
│ │ ├── postgres/ # PostgreSQL database services
│ │ └── rag_services/ # RAG implementation with vector storage
│ │ ├── controller/ # API controllers for RAG services
│ │ ├── models/ # Document models and graph builders
│ │ └── services/ # Core RAG service implementations
│ └── utils/ # Utility functions and helpers
│
├── test/ # Unit tests and integration tests
│ ├── services/
│ │ └── rag_services/
│ │     └── services/
│ │         └── test_multi_rag_service.py    # RAG service tests (96% coverage)
│ ├── bots/
│ │ └── handlers/
│ │     ├── test_rag_process_minimal.py      # Minimal RAG process tests (95% coverage)
│ │     └── test_rag_process.py              # Extended RAG tests (needs fixing)
│ └── chunking_test.py                       # Document chunking tests (needs fixing)
│
├── main.py # Main entry point of the FastApi application
├── Dockerfile # Container definition
├── requirements.txt # Python dependencies
├── pyproject.toml # Config & dependencies cho uv
├── uv.lock # Locked versions (frozen by uv)
└── SECURITY.md # Security guidelines

```

## Database Configuration

The project now uses pure SQLAlchemy for database operations. Database configuration is managed through the `src/config/database_config.py` file.

### Key Database Components

- `DatabaseConfig` class: Contains all database connection parameters

- `Base`: SQLAlchemy declarative base for model definitions

- `db`: A modern database interface that provides helper methods for common operations

- `get_db()`: FastAPI dependency function that provides a session for routes

- `get_db_context()`: Context manager for database sessions outside of API routes

### Database Usage Examples

```python

# In FastAPI routes (dependency injection)

@router.get("/items")

def  get_items(db: Session = Depends(get_db)):

items = db.query(Item).all()

return items

  

# Using context manager

from src.services.postgres.db_utils import get_db_context

  

with get_db_context() as session:

items = session.query(Item).all()

  

# Using database models with operations

from src.services.postgres.models.tables.my_model import MyModel

  

# Create

new_item = MyModel.create(name="Test", db_session=None) # Will use default session

  

# Find

items = MyModel.find_by_filter(name="Test")
```

---

### Run pytest

```python
# Install the pytest plugin for generating Markdown reports
pip install pytest-md-report

# Run all tests in the tests directory and output the result as a Markdown file (report.md)
pytest --md-report tests
```

---

## Testing Guide

This project uses **pytest** as the primary testing framework with comprehensive coverage analysis and additional testing tools.

### Testing Framework

- **pytest**: Core testing framework with asyncio support
- **pytest-cov**: Coverage analysis and reporting
- **pytest-mock**: Advanced mocking capabilities
- **pytest-xdist**: Parallel test execution
- **factory-boy**: Test data generation

### Running Tests

#### Basic Test Commands

```bash
# Run all working tests
pytest tests/services/ tests/bots/handlers/test_rag_process_minimal.py -v

# Run tests with coverage report
uv run coverage run -m pytest tests/services/ tests/bots/handlers/test_rag_process_minimal.py
uv run coverage report --show-missing

# Run tests in parallel (2 workers)
pytest -n 2 tests/services/ tests/bots/handlers/test_rag_process_minimal.py

# Generate HTML coverage report
uv run coverage run -m pytest tests/services/ tests/bots/handlers/test_rag_process_minimal.py
uv run coverage html
```

#### Advanced Test Commands

```bash
# Run with detailed coverage missing lines
uv run coverage run -m pytest tests/ -v
uv run coverage report --show-missing

# Run specific test class
pytest tests/services/rag_services/services/test_multi_rag_service.py::TestMultiRagService -v

# Run with pytest markers (if configured)
pytest -m "not slow" tests/

# Generate markdown report
pytest --md-report --md-report-output=test_report.md tests/
```

### Current Test Status

- **Total Tests**: 8 passing
- **Test Coverage**: 33% overall
- **Key Test Files**:
  - `src/test/services/rag_services/services/test_multi_rag_service.py` - 96% coverage
  - `src/test/bots/handlers/test_rag_process_minimal.py` - 95% coverage

### Test Structure

```
src/test/
├── services/
│   └── rag_services/
│       └── services/
│           └── test_multi_rag_service.py    # RAG service tests
├── bots/
│   └── handlers/
│       ├── test_rag_process_minimal.py      # Minimal RAG process tests
│       └── test_rag_process.py              # (needs fixing)
└── chunking_test.py                         # (needs fixing)
```

### Writing Tests

#### Test Guidelines

1. **Use async/await** for testing async functions
2. **Mock external dependencies** (databases, APIs, file systems)
3. **Follow AAA pattern**: Arrange, Act, Assert
4. **Use descriptive test names** that explain the scenario
5. **Test both success and error cases**

#### Example Test Structure

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

class TestYourFunction:
    @pytest.fixture
    def mock_dependency(self):
        return MagicMock()
    
    @pytest.mark.asyncio
    @patch("your.module.external_dependency")
    async def test_successful_scenario(self, mock_external, mock_dependency):
        # Arrange
        mock_external.return_value = "expected_result"
        
        # Act
        result = await your_function(mock_dependency)
        
        # Assert
        assert result == "expected_result"
        mock_external.assert_called_once()
```

### CI/CD Integration

Tests are integrated into the CI/CD pipeline but currently commented out in `.github/workflows/ci-dev.yaml`. To enable:

1. Uncomment the test section in `ci-dev.yaml`
2. Ensure all dependencies are properly mocked
3. Fix broken test files (`test_rag_process.py`, `chunking_test.py`)

Example CI test configuration:
```yaml
- name: Run Tests
  run: |
    uv sync --extra dev
    pytest --cov=src --cov-report=term-missing src/test/services/ src/test/bots/handlers/test_rag_process_minimal.py
```

### Troubleshooting Tests

#### Common Issues

1. **Import Errors**: Ensure proper mocking of external dependencies before imports
2. **Async Warnings**: Use `AsyncMock` for async methods
3. **Database Connections**: Mock `psycopg.connect` and database operations
4. **GCP Services**: Mock `google.auth.default` and GCP clients

#### Debug Commands

```bash
# Run with verbose output and show warnings
pytest -v -s --tb=short src/test/

# Run single test with full traceback
pytest --tb=long src/test/path/to/specific_test.py::TestClass::test_method

# Check test discovery
pytest --collect-only src/test/
```

## Run All Services with Docker Compose

You can run the main app, document handler, and docling-serve together using Docker Compose. All services are defined in `docker-compose.yml` and use the unified `Dockerfile.debug` (except docling-serve, which uses a public image).

```bash
docker compose up --build
```

### Services

- **main-app**: Main FastAPI application (port 5000)
- **document-handler**: Document handler microservice (port 8080)
- **docling-serve**: Docling document conversion API (port 8000, public image)

All services share environment variables from `.env.local`.

**Internal Networking:**  
Other services can reach docling-serve at `http://docling-serve:8000` (Docker Compose service name).

**Example:**  
Set in your `.env.local`:

```
DOCLING_SERVE_URL=http://docling-serve:8000
```

to allow the main app or document handler to call the docling-serve API.

---

## Run a Single Service Manually (for development)

You can run either the main app or the document handler using the unified `Dockerfile.debug` by setting the `SERVICE` environment variable:

- **Main app (default):**

  ```bash
  docker build -f Dockerfile.debug -t main-app .
  docker run -p 5000:5000 --env-file .env.local main-app
  ```

- **Document handler:**

  ```bash
  docker build -f Dockerfile.debug -t document-handler --build-arg SERVICE=document-handler .
  docker run -p 8080:8080 --env SERVICE=document-handler --env-file .env.local document-handler
  ```

---

## Run the Docling-Serve Service (docker)

Docling-serve is a microservice for document conversion (e.g., PDF, DOCX, PPTX) to markdown via API. It is used by other services in this project for document processing.

1. Pull the public docling-serve image:

```bash
docker pull ghcr.io/docling-project/docling-serve-cpu:main
```

2. Run the docling-serve service:

```bash
docker run -p 8000:8000 -e DOCLING_SERVE_ENABLE_REMOTE_SERVICES=true -e DOCLING_SERVE_ENG_LOC_NUM_WORKERS=2 -e DOCLING_SERVE_ENABLE_UI=true -e UVICORN_PORT=8000 ghcr.io/docling-project/docling-serve-cpu:main
```

- The service will be available at `http://localhost:8000` (or the port you map).
- Set the environment variable `DOCLING_SERVE_URL=http://localhost:8000` in your `.env.local` or deployment environment so other services can call the docling API.

**Example API usage:**

- POST a file to `/convert` to receive markdown output.
