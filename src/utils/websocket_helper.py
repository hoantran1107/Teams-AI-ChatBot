import asyncio
import json
import logging
import mimetypes
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import httpx
import websockets

from src.config.settings import docling_serve_url
from src.constants.docling_constant import DoclingConstant, DoclingWebSocketClientConstant

_logger = logging.getLogger(__name__)


class DoclingWebSocketClient:
    """WebSocket client for docling-serve service with subscription pattern."""

    def __init__(self) -> None:
        """Initialize DoclingWebSocketClient with WebSocket connection parameters."""
        # Convert HTTP URL to WebSocket URL
        self.websocket_url = docling_serve_url.replace("http", "ws") + "/ws"
        self.connection: Any = None
        self.subscriptions: dict[str, Callable[[dict[str, Any]], Awaitable[None]]] = {}
        self.is_connected = False

    async def connect(self) -> None:
        """Establish WebSocket connection."""
        try:
            self.connection = await websockets.connect(
                self.websocket_url,
                ping_interval=DoclingWebSocketClientConstant.PING_INTERVAL,
                ping_timeout=DoclingWebSocketClientConstant.PING_TIMEOUT,
                close_timeout=DoclingWebSocketClientConstant.CLOSE_TIMEOUT,
            )
            self.is_connected = True
            _logger.info(f"WebSocket connected to {self.websocket_url}")
        except Exception as e:
            _logger.error(f"Failed to connect WebSocket: {e}")
            raise

    async def disconnect(self) -> None:
        """Close WebSocket connection."""
        if self.connection:
            self.is_connected = False
            await self.connection.close()
            _logger.info("WebSocket disconnected")

    async def subscribe(self, topic: str, callback: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        """Subscribe to a topic with callback function."""
        if not self.connection:
            raise ConnectionError(DoclingWebSocketClientConstant.WEBSOCKET_NOT_CONNECTED)

        # Send subscription message
        subscribe_msg = {
            "action": "subscribe",
            "topic": topic,
        }
        await self.connection.send(json.dumps(subscribe_msg))

        # Store callback
        self.subscriptions[topic] = callback
        _logger.info(f"Subscribed to topic: {topic}")

    async def unsubscribe(self, topic: str) -> None:
        """Unsubscribe from a topic."""
        if not self.connection:
            return

        # Send unsubscribe message
        unsubscribe_msg = {
            "action": "unsubscribe",
            "topic": topic,
        }
        await self.connection.send(json.dumps(unsubscribe_msg))

        # Remove callback
        if topic in self.subscriptions:
            del self.subscriptions[topic]
        _logger.info(f"Unsubscribed from topic: {topic}")

    async def publish(self, topic: str, message: dict[str, Any]) -> None:
        """Publish message to a topic."""
        if not self.connection:
            raise ConnectionError(DoclingWebSocketClientConstant.WEBSOCKET_NOT_CONNECTED)

        publish_msg = {
            "action": "publish",
            "topic": topic,
            "message": message,
        }
        await self.connection.send(json.dumps(publish_msg))
        _logger.debug(f"Published to topic {topic}: {message}")

    async def listen_for_messages(self, timeout_seconds: float = 30.0) -> None:
        """Listen for incoming messages and handle subscriptions."""
        if not self.connection:
            raise ConnectionError(DoclingWebSocketClientConstant.WEBSOCKET_NOT_CONNECTED)

        try:
            while self.is_connected:
                try:
                    message = await asyncio.wait_for(self.connection.recv(), timeout=timeout_seconds)
                    data = json.loads(message)
                    _logger.debug(f"Received message: {data}")

                    # Handle different message types
                    await self._handle_message(data)

                except TimeoutError:
                    # Send ping to keep connection alive
                    if self.is_connected:
                        await self.connection.ping()
                        _logger.debug("Sent ping to keep connection alive")
                except json.JSONDecodeError as e:
                    _logger.error(f"Failed to decode WebSocket message: {e}")

        except websockets.exceptions.ConnectionClosed:
            _logger.info("WebSocket connection closed")
            self.is_connected = False
        except OSError as e:
            _logger.error(f"Network error in message listener: {e}")
            self.is_connected = False

    async def _handle_subscription_callback(self, topic: str, data: dict[str, Any]) -> None:
        """Handle callback for a subscription topic.

        Args:
            topic: The topic for the callback
            data: The data to pass to the callback

        """
        try:
            await self.subscriptions[topic](data.get("message", {}))
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            _logger.error(f"Data processing error in subscription callback for {topic}: {e}")
        except asyncio.CancelledError:
            raise
        except RuntimeError as e:
            _logger.error(f"Runtime error in subscription callback for {topic}: {e}")

    async def _handle_status_callback(self, topic: str, data: dict[str, Any]) -> None:
        """Handle callback for a status subscription.

        Args:
            topic: The status topic for the callback
            data: The data to pass to the callback

        """
        try:
            await self.subscriptions[topic](data)
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            _logger.error(f"Data processing error in status callback for {topic}: {e}")
        except asyncio.CancelledError:
            raise
        except RuntimeError as e:
            _logger.error(f"Runtime error in status callback for {topic}: {e}")

    async def _handle_message(self, data: dict[str, Any]) -> None:
        """Handle incoming messages based on type."""
        msg_type = data.get("type")
        topic = data.get("topic")

        match msg_type:
            case "subscription":
                # Handle subscription confirmation
                _logger.info(f"Subscription confirmed for topic: {topic}")

            case "message":
                # Handle topic message
                if topic in self.subscriptions:
                    await self._handle_subscription_callback(topic, data)
                else:
                    _logger.warning(f"Received message for unsubscribed topic: {topic}")

            case "error":
                error_msg = data.get("message", "Unknown error")
                _logger.error(f"WebSocket error: {error_msg}")

            case "status":
                # Handle status updates
                status = data.get("status")
                task_id = data.get("task_id")
                _logger.info(f"Task {task_id} status: {status}")

                # Notify status subscribers
                status_topic = f"status.{task_id}" if task_id else "status"
                if status_topic in self.subscriptions:
                    await self._handle_status_callback(status_topic, data)

            case _:
                _logger.warning(f"Unknown message type: {msg_type}")


def _validate_file_type(file_path: str) -> tuple[str, Path]:
    """Validate the file type of the file."""
    file = Path(file_path)
    ext = file.suffix.lower().lstrip(".")
    if ext not in DoclingConstant.FROM_FORMAT:
        error_msg = f"Unsupported file type: .{ext}"
        raise ValueError(error_msg)
    return ext, file


async def convert_file_via_docling_websocket_subscription(file_path: str) -> tuple[bool, str]:
    """Convert a file to markdown using docling-serve via HTTP upload and WebSocket status monitoring.

    Returns:
        tuple[bool, str]: (success, content_or_error_message)
        - If success=True: content is markdown string
        - If success=False: content is error message

    """
    task_id = None
    md_content = None

    try:
        ext, file = _validate_file_type(file_path)
        mime, _ = mimetypes.guess_type(file.name)
        mime = mime or "application/octet-stream"
        file_bytes = file.read_bytes()

        async with httpx.AsyncClient(timeout=120.0) as client:
            # 1. Upload file, get task_id
            resp = await client.post(
                f"{docling_serve_url}/v1/convert/file/async",
                files={"files": (file.name, file_bytes, mime)},
                data={"from_format": ext, "do_ocr": False, "image_export_mode": "placeholder"},
            )
            _ = resp.raise_for_status()
            task_id = resp.json().get("task_id")

        # 2. Subscribe via WebSocket for task status
        ws_url = f"{docling_serve_url.replace('http', 'ws')}/v1/status/ws/{task_id}"
        _logger.debug("WebSocket URL: %s", ws_url)
        try:
            async with websockets.connect(ws_url, ping_interval=30, ping_timeout=10, close_timeout=10) as ws:
                while True:
                    msg = await asyncio.wait_for(ws.recv(), timeout=300)
                    payload = json.loads(msg)
                    status = payload.get("task", {}).get("task_status")
                    if status == "success":
                        break
                    if status == "failure":
                        error_msg = payload.get("task", {}).get("error", "Unknown error")
                        return False, f"Conversion failed: {error_msg}"
        except (websockets.exceptions.WebSocketException, OSError, json.JSONDecodeError) as ws_exc:
            return False, f"WebSocket connection failed: {ws_exc}"

        # 3. Download markdown result
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                result = await client.get(f"{docling_serve_url}/v1/result/{task_id}")
                _ = result.raise_for_status()
                md_content = result.json().get("document", {}).get("md_content")
                if not md_content:
                    return False, "No markdown content returned from result endpoint"
                return True, md_content
        except (httpx.HTTPError, json.JSONDecodeError, KeyError) as e:
            return False, f"Failed to download result: {e}"
    except (ValueError, OSError, TypeError) as e:
        return False, f"Unexpected error: {e}"
    finally:
        # 4. Clear results to reduce memory leak
        if task_id:
            try:
                _logger.debug("Clearing results for task")
                async with httpx.AsyncClient(timeout=30.0) as client:
                    _ = await client.get(f"{docling_serve_url}/v1/clear/results")
            except (httpx.HTTPError, OSError):
                _logger.exception("Cleanup failed")
