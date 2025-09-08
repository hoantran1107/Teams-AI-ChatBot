# Import necessary modules for testing
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Mock external dependencies before importing the module
with patch("psycopg.connect"), patch("google.auth.default"), patch("google.cloud.storage.Client"):
    try:
        from src.bots.handlers.rag_process import process_rag_query
    except ImportError as e:
        print(f"Required dependencies not found: {e}")
        raise


class TestProcessRagQuery:
    """Minimal unit tests for process_rag_query function."""

    @pytest.fixture
    def mock_context(self):
        """Create a mock context with minimal attributes."""
        context = MagicMock()
        context.activity = MagicMock()
        context.activity.from_property = MagicMock()
        context.activity.from_property.id = "test_user"
        context.activity.from_property.name = "Test User"
        context.data = {"language": "en"}
        return context

    @pytest.fixture
    def mock_state(self):
        """Create a mock state with minimal attributes."""
        state = MagicMock()
        state.conversation = {"session_id": "test_session"}
        state.user = MagicMock()
        state.user.analysis_mode = False
        state.user.data_sources = []
        return state

    @pytest.mark.asyncio
    @patch("src.bots.handlers.rag_process.StreamingResponse")
    @patch("src.bots.handlers.rag_process.MultiRagService")
    @patch("src.bots.handlers.rag_process.process_stream_chunks")
    @patch("src.bots.handlers.rag_process._prepare_data_sources_from_state")
    @patch("src.bots.handlers.rag_process.add_citations_to_response")
    async def test_basic_success(
        self,
        mock_add_citations,
        mock_prepare_data_sources,
        mock_process_chunks,
        mock_multi_rag_service,
        mock_streaming_cls,
        mock_context,
        mock_state,
    ):
        """Test basic successful execution."""
        # Setup mocks
        mock_streaming = MagicMock()
        mock_streaming.queue_informative_update = AsyncMock()
        mock_streaming.wait_for_queue = AsyncMock()
        mock_streaming.end_stream = AsyncMock()
        mock_streaming.message = "Test response"
        mock_streaming_cls.return_value = mock_streaming
        mock_process_chunks.return_value = (None, None, 0)
        mock_prepare_data_sources.return_value = []

        # Act
        result = await process_rag_query("What is 1+1?", mock_context, mock_state)

        # Assert
        assert result == "Test response"
        mock_streaming.end_stream.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.bots.handlers.rag_process.StreamingResponse")
    @patch("src.bots.handlers.rag_process._logger")
    async def test_exception_handling(self, mock_logger, mock_streaming_cls, mock_context, mock_state):
        """Test that exceptions are handled gracefully."""
        # Setup to raise exception
        mock_streaming = MagicMock()
        mock_streaming.queue_informative_update = AsyncMock(side_effect=Exception("Test error"))
        mock_streaming.end_stream = AsyncMock()
        mock_streaming.message = "Error response"
        mock_streaming_cls.return_value = mock_streaming

        with patch("src.bots.handlers.rag_process._prepare_data_sources_from_state", return_value=[]):
            # Act
            result = await process_rag_query("Test query", mock_context, mock_state)

            # Assert
            assert result == "Error response"
            mock_logger.error.assert_called()
            mock_streaming.end_stream.assert_called_once()
