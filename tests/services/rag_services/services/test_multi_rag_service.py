# Import necessary modules for testing and processing
import os
from unittest.mock import MagicMock, patch

import pytest
from dotenv import load_dotenv

# Set comprehensive environment variables for testing before any imports
os.environ.setdefault("DB_USER", "test_user")
os.environ.setdefault("DB_PASSWORD", "test_password")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "test_db")
os.environ.setdefault("VECTOR_DB_NAME", "test_vector_db")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "test_key")
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
os.environ.setdefault("AZURE_CHAT_DEPLOYMENT_NAME", "test_deployment")
os.environ.setdefault("AZURE_EMBEDDING_DEPLOYMENT_NAME", "test_embedding")
os.environ.setdefault("DEBUG", "false")
os.environ.setdefault("TESTING", "true")
os.environ.setdefault("APP_PORT", "5000")
os.environ.setdefault("DOCUMENT_HANDLER_DOMAIN", "test.domain.com")

# Create a mock for the fastapi_settings to avoid Pydantic validation
mock_fastapi_settings = MagicMock()
mock_db = MagicMock()
mock_db.database_url = "postgresql://test:test@localhost:5432/test"
mock_db.vector_db_url = "postgresql://test:test@localhost:5432/test_vector"
mock_db.vector_db_url_async = "postgresql+asyncpg://test:test@localhost:5432/test_vector"
mock_db.engine_options = {}
mock_db.database_ssl_context = None
mock_fastapi_settings.db = mock_db

# Mock all database-related components and the fastapi_settings
with (
    patch("psycopg.connect") as mock_connect,
    patch("sqlalchemy.create_engine") as mock_create_engine,
    patch("sqlalchemy.ext.asyncio.create_async_engine") as mock_create_async_engine,
    patch("src.config.fastapi_config.fastapi_settings", mock_fastapi_settings),
):
    mock_connect.return_value = MagicMock()
    mock_create_engine.return_value = MagicMock()
    mock_create_async_engine.return_value = MagicMock()

    try:
        from src.services.rag_services.services.multiple_rag_sources import MultiRagService
    except ImportError as e:
        print(f"Required dependencies not found: {e}")
        raise

load_dotenv()


class TestMultiRagService:
    """Unit tests for MultiRagService.stream_response method."""

    @pytest.fixture
    def basic_mock_stream_generator(self):
        """Create a basic mock generator for simple text responses."""

        async def generator(*args, **kwargs):
            yield {"msg": "2", "session_id": "test_session"}

        return generator

    @pytest.fixture
    def citation_mock_stream_generator(self):
        """Create a mock generator that includes both text and citation data."""

        async def generator(*args, **kwargs):
            yield {"msg": "The answer is 2", "session_id": "test_session"}
            yield {
                "citation": [
                    {
                        "document_id": "doc1",
                        "text": "1+1=2",
                        "topic": "Mathematics",
                        "document_collection": "Basic Math",
                    },
                ],
                "session_id": "test_session",
            }

        return generator

    @pytest.fixture
    def empty_mock_stream_generator(self):
        """Create an empty mock generator to test no response scenarios."""

        async def generator(*args, **kwargs):
            # Empty async generator - will not yield anything
            for _ in []:  # Empty loop ensures no yielding
                yield

        return generator

    @pytest.mark.asyncio
    @patch("src.services.rag_services.services.RAGService.stream_response")
    async def test_basic_success_scenario(self, mock_super_stream, basic_mock_stream_generator):
        """Test Case 1: Basic Success Scenario - The '1+1=?' Test."""
        # Arrangement
        mock_super_stream.return_value = basic_mock_stream_generator()
        service = MultiRagService()

        # Define input arguments
        question = "1+1=?"
        session_id = "test_session_123"
        user_id = "test_user"
        data_sources = [{"source_name": "math_db", "user_id": None}]

        # Action
        results = []
        async for chunk in service.stream_response(
            question=question,
            session_id=session_id,
            user_id=user_id,
            data_sources=data_sources,
            analysis_mode=False,
        ):
            results.append(chunk)

        # Assertion
        assert len(results) == 1
        assert results[0]["msg"] == "2"
        assert results[0]["session_id"] == "test_session"

        # Verify that the mocked method was called exactly once
        mock_super_stream.assert_called_once()

        # Check that super().stream_response was called with correct arguments
        call_args = mock_super_stream.call_args
        assert call_args[0][0] == question  # First positional arg is question
        assert call_args[0][1] == session_id  # Second positional arg is session_id
        assert call_args[0][2] == user_id  # Third positional arg is user_id
        assert call_args[1]["requested_sources"] == data_sources
        assert call_args[1]["analyze_table"] is False
        assert call_args[1]["using_memory"] is False

    @pytest.mark.asyncio
    @patch("src.services.rag_services.services.RAGService.stream_response")
    async def test_handling_citations(self, mock_super_stream, citation_mock_stream_generator):
        """Test Case 2: Handling Citations - Ensure citation data is processed correctly."""
        # Arrangement
        mock_super_stream.return_value = citation_mock_stream_generator()
        service = MultiRagService()

        # Action
        results = []
        async for chunk in service.stream_response(
            question="What is 1+1?",
            data_sources=[{"source_name": "math_reference", "user_id": None}],
        ):
            results.append(chunk)

        # Assertion
        assert len(results) == 2

        # Check first chunk (message)
        assert results[0]["msg"] == "The answer is 2"
        assert results[0]["session_id"] == "test_session"

        # Check second chunk (citation)
        assert "citation" in results[1]
        citation_data = results[1]["citation"][0]
        assert citation_data["document_id"] == "doc1"
        assert citation_data["text"] == "1+1=2"
        assert citation_data["topic"] == "Mathematics"
        assert citation_data["document_collection"] == "Basic Math"

    @pytest.mark.asyncio
    @patch("src.services.rag_services.services.RAGService.stream_response")
    async def test_different_input_parameters(self, mock_super_stream, basic_mock_stream_generator):
        """Test Case 3: Handling Different Input Parameters"""
        # Arrangement
        mock_super_stream.return_value = basic_mock_stream_generator()
        service = MultiRagService()

        # Define test parameters
        data_sources = [
            {"source_name": "database_1", "user_id": "user123"},
            {"source_name": "database_2", "user_id": None},
        ]
        analysis_mode = True
        language = "es"

        # Action
        results = []
        async for chunk in service.stream_response(
            question="Test question with parameters",
            session_id="param_test_session",
            user_id="param_user",
            user_name="Test User",
            data_sources=data_sources,
            analysis_mode=analysis_mode,
            language=language,
        ):
            results.append(chunk)

        # Assertion
        assert len(results) == 1

        # Inspect the arguments passed to the mocked super().stream_response
        call_args = mock_super_stream.call_args
        assert call_args[1]["requested_sources"] == data_sources
        assert call_args[1]["analyze_table"] is True
        assert call_args[1]["language"] == language
        assert call_args[1]["using_memory"] is False

    @pytest.mark.asyncio
    @patch("src.services.rag_services.services.RAGService.stream_response")
    async def test_handling_empty_response(self, mock_super_stream, empty_mock_stream_generator):
        """Test Case 4: Handling Empty or No Response."""
        # Arrangement
        mock_super_stream.return_value = empty_mock_stream_generator()
        service = MultiRagService()

        # Action
        results = []
        async for chunk in service.stream_response(question="Question with no response", data_sources=[]):
            results.append(chunk)

        # Assertion
        assert len(results) == 0

        # Verify the method was still called
        mock_super_stream.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.services.rag_services.services.RAGService.stream_response")
    async def test_default_parameters(self, mock_super_stream, basic_mock_stream_generator):
        """Test that default parameters are handled correctly when not provided."""
        # Arrangement
        mock_super_stream.return_value = basic_mock_stream_generator()
        service = MultiRagService()

        # Action - call with minimal parameters
        results = []
        async for chunk in service.stream_response(question="Minimal test"):
            results.append(chunk)

        # Assertion
        assert len(results) == 1

        # Check default values were passed correctly
        call_args = mock_super_stream.call_args
        assert call_args[1]["requested_sources"] == []  # Default empty list
        assert call_args[1]["analyze_table"] is False  # Default False
        assert call_args[1]["language"] == "en"  # Default language
        assert call_args[1]["using_memory"] is False

    @pytest.mark.asyncio
    @patch("src.services.rag_services.services.RAGService.stream_response")
    async def test_kwargs_processing(self, mock_super_stream, basic_mock_stream_generator):
        """Test that input_kwargs are processed correctly (pop operations)."""
        # Arrangement
        mock_super_stream.return_value = basic_mock_stream_generator()
        service = MultiRagService()

        # Action - pass extra kwargs that should be processed/removed
        results = []
        async for chunk in service.stream_response(
            question="Test kwargs",
            data_sources=[{"source_name": "test"}],
            analysis_mode=True,
            language="fr",
            full_response=["existing", "responses"],
            extra_param="should_be_ignored",  # This shouldn't cause issues
        ):
            results.append(chunk)

        # Assertion
        assert len(results) == 1

        # Verify correct parameters were passed to super()
        call_args = mock_super_stream.call_args
        assert call_args[1]["requested_sources"] == [{"source_name": "test"}]
        assert call_args[1]["analyze_table"] is True
        assert call_args[1]["language"] == "fr"
        assert call_args[1]["full_response"] == ["existing", "responses"]
        # extra_param should not appear in the call to super()
        assert "extra_param" not in call_args[1]

    @pytest.mark.asyncio
    @patch("src.services.rag_services.services.RAGService.stream_response")
    async def test_with_database_session(self, mock_super_stream, basic_mock_stream_generator):
        """Test Case: Database Session Parameter Handling."""
        # Arrangement
        mock_super_stream.return_value = basic_mock_stream_generator()
        service = MultiRagService()
        mock_db = MagicMock()

        # Action
        results = []
        async for chunk in service.stream_response(
            question="Test with db",
            db=mock_db,
            data_sources=[{"source_name": "test"}],
        ):
            results.append(chunk)

        # Assertion
        assert len(results) == 1
        call_args = mock_super_stream.call_args
        assert call_args[1]["db"] == mock_db

    @pytest.mark.asyncio
    @patch("src.services.rag_services.services.RAGService.stream_response")
    async def test_exception_handling(self, mock_super_stream):
        """Test Case: Exception Handling in Stream Response."""
        # Arrangement
        mock_super_stream.side_effect = Exception("Test exception")
        service = MultiRagService()

        # Action & Assertion
        with pytest.raises(Exception, match="Test exception"):
            async for _ in service.stream_response(question="Test exception"):
                ...

    @pytest.mark.asyncio
    @patch("src.services.rag_services.services.RAGService.stream_response")
    async def test_parameter_mapping_correctness(self, mock_super_stream, basic_mock_stream_generator):
        """Test Case: Verify correct parameter mapping between MultiRagService and parent class."""
        # Arrangement
        mock_super_stream.return_value = basic_mock_stream_generator()
        service = MultiRagService()

        # Define comprehensive test parameters
        test_params = {
            "question": "Test parameter mapping",
            "session_id": "mapping_test_session",
            "user_id": "mapping_user",
            "user_name": "Mapping Test User",
            "data_sources": [{"source_name": "mapping_db", "user_id": "user123"}],
            "analysis_mode": True,
            "language": "es",
        }

        # Action
        results = []
        async for chunk in service.stream_response(**test_params):
            results.append(chunk)

        # Assertion
        assert len(results) == 1
        call_args = mock_super_stream.call_args

        # Verify positional arguments
        assert call_args[0][0] == test_params["question"]
        assert call_args[0][1] == test_params["session_id"]
        assert call_args[0][2] == test_params["user_id"]
        assert call_args[0][3] == test_params["user_name"]

        # Verify keyword arguments mapping
        assert call_args[1]["requested_sources"] == test_params["data_sources"]
        assert call_args[1]["analyze_table"] == test_params["analysis_mode"]
        assert call_args[1]["language"] == test_params["language"]
        assert call_args[1]["using_memory"] is False  # Always False in MultiRagService
        assert call_args[1]["full_response"] == []  # Default empty list

    @pytest.mark.asyncio
    @patch("src.services.rag_services.services.RAGService.stream_response")
    async def test_full_response_parameter_handling(self, mock_super_stream, basic_mock_stream_generator):
        """Test Case: Handling of full_response parameter."""
        # Arrangement
        mock_super_stream.return_value = basic_mock_stream_generator()
        service = MultiRagService()
        existing_responses = ["Response 1", "Response 2"]

        # Action
        results = []
        async for chunk in service.stream_response(
            question="Test full response",
            data_sources=[{"source_name": "test"}],
            full_response=existing_responses,
        ):
            results.append(chunk)

        # Assertion
        assert len(results) == 1
        call_args = mock_super_stream.call_args
        assert call_args[1]["full_response"] == existing_responses
