from src.config.settings import docling_serve_url

class DoclingConstant:
    DO_OCR: str = "false"
    FROM_FORMAT: list[str] = ["docx", "pptx", "html", "image", "pdf", "asciidoc", "md", "xlsx"]
    VERSION: str = "v1"
    CONVERT_FILE_ASYNC: str = f"{docling_serve_url}/{VERSION}/convert/file/async"
    STATUS_POLL: str = f"{docling_serve_url}/{VERSION}/status/poll"
    RESULT: str = f"{docling_serve_url}/{VERSION}/result"
    SUPPORTED_FILES: list[str] = [".docx", ".pptx", ".html", ".pdf", ".asciidoc", ".md", ".xlsx"]
    
class DoclingException(Exception):
    pass

class WebSocketClientException(Exception):
    pass

class DoclingWebSocketClientConstant:
    PING_INTERVAL: int = 30
    PING_TIMEOUT: int = 10
    CLOSE_TIMEOUT: int = 10
    WEBSOCKET_NOT_CONNECTED: str = "WebSocket not connected"