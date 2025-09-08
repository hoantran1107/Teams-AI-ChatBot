import base64
import email
import logging
import re
import subprocess
import tempfile
import unicodedata
from email import policy
from pathlib import Path

from bs4 import BeautifulSoup

_logger = logging.getLogger("MSWordHelper")


def sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing special characters and keeping only alphanumeric chars.

    Args:
            filename: Original filename

    Returns:
            Sanitized filename

    """
    # Remove extension if present
    name = Path(filename).stem

    # Remove accents/diacritics
    name = unicodedata.normalize("NFKD", name).encode("ASCII", "ignore").decode("ASCII")

    # Replace special chars with underscore and remove multiple underscores
    name = re.sub(r"[^\w\s-]", "_", name)
    name = re.sub(r"[-\s]+", "_", name)
    name = re.sub(r"_+", "_", name)

    # Remove leading/trailing underscores
    name = name.strip("_")

    return name


def convert_doc_to_docx(input_file: str, output_dir: str) -> bool:
    """Convert DOC file to DOCX, handling different file types.

    Args:
            input_file: Path to the DOC file to convert
            output_dir: Output directory for the DOCX file

    Returns:
            bool: True if conversion is successful, False if failed

    """
    _logger.info("Processing file: %s", input_file)

    # Ensure output directory exists
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Read first bytes to check file type
    try:
        with Path(input_file).open(encoding="utf-8", errors="replace") as f:
            file_start = f.read(1000)  # Read first 1000 characters for checking
    except Exception:
        _logger.exception("\tError reading file")
        return False

    # Check if it's a MIME file
    is_mime_file = "MIME-Version" in file_start or "Content-Type: multipart" in file_start

    # Process based on file type
    if is_mime_file:
        return convert_mime_doc_to_docx(input_file, output_dir)
    return convert_regular_doc_to_docx(input_file, output_dir)


def convert_regular_doc_to_docx(input_file: str, output_dir: str) -> bool:
    """Convert regular DOC file to DOCX using LibreOffice."""
    # Get absolute paths
    input_path = Path(input_file).resolve()
    output_dir_path = Path(output_dir).resolve()

    # Perform conversion
    command = f'libreoffice --headless --convert-to docx:"MS Word 2007 XML" --outdir {output_dir_path} {input_path}'

    try:
        result = subprocess.run(command, check=False, shell=True, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        _logger.exception("\tConversion timed out after 5 minutes")
        return False

    # Check result
    output_file = output_dir_path / f"{Path(input_file).stem}.docx"
    success = output_file.exists()

    if success:
        _logger.debug("\tSuccessfully converted to DOCX: %s", output_file)
    else:
        _logger.warning("\tConversion failed: %s", result.stderr)

    return success


def convert_mime_doc_to_docx(mime_file: str, output_dir: str) -> bool:
    """Convert MIME file to DOCX with image processing."""
    # Read MIME file
    try:
        with Path(mime_file).open(encoding="utf-8", errors="replace") as f:
            email_content = f.read()
    except Exception:
        _logger.exception("\tError reading MIME file")
        return False

    # Parse email is library for parse mine to many parts
    msg = email.message_from_string(email_content, policy=policy.default)

    # Find HTML content and images
    html_content = None
    image_data: dict[str, str] = {}

    for part in msg.walk():
        content_type = part.get_content_type()

        if content_type == "text/html":
            html_content = part.get_content()

        elif content_type in ["application/octet-stream", "image/png", "image/jpeg", "image/gif"]:
            content_location = part.get("Content-Location")
            if content_location:
                image_id = Path(content_location).name

                # Get image data
                img_bytes = part.get_payload(decode=True)
                if img_bytes:
                    # Determine MIME type from data
                    mime_type = "image/png"  # Default to PNG
                    if isinstance(img_bytes, bytes) and img_bytes.startswith(b"\xff\xd8"):
                        mime_type = "image/jpeg"
                    elif isinstance(img_bytes, bytes) and img_bytes.startswith(b"GIF8"):
                        mime_type = "image/gif"

                    # Encode data as base64
                    base64_data = base64.b64encode(img_bytes).decode("utf-8")
                    data_uri = f"data:{mime_type};base64,{base64_data}"
                    image_data[image_id] = data_uri

    if not html_content:
        _logger.error("\tNo HTML content found in MIME file")
        return False

    # Fix encoded characters
    html_content = html_content.replace("=3D", "=")

    # Parse HTML
    soup = BeautifulSoup(html_content, "html.parser")

    # Fix image paths with Base64 data
    updated_count = 0
    for img in soup.find_all("img"):
        src = img.get("src")
        alt = img.get("alt")
        data_src = img.get("data-image-src")

        for image_id, data_uri in image_data.items():
            if (src and image_id in src) or (alt and image_id in alt) or (data_src and image_id in data_src):
                img["src"] = data_uri
                updated_count += 1
                break

    # Log the number of updated images
    _logger.debug(f"\tUpdated {updated_count} image references in HTML")

    # Create sanitized output filename
    sanitized_name = sanitize_filename(Path(mime_file).name)

    # Save modified HTML to temp file
    html_file = Path(tempfile.gettempdir()) / f"{sanitized_name}.html"
    with html_file.open(mode="w", encoding="utf-8") as f:
        f.write(str(soup))

    # Try primary conversion method
    try:
        subprocess.run(
            f'libreoffice --headless --convert-to docx:"MS Word 2007 XML" {html_file} --outdir {output_dir}',
            check=False,
            shell=True,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        _logger.error("\tConversion timed out after 5 minutes")
        return False

    output_docx = Path(output_dir) / f"{sanitized_name}.docx"
    if Path(output_docx).exists():
        _logger.info(f"\tSuccessfully converted to DOCX: {output_docx}")
        return True
    # Try alternative method if failed
    return try_alternative_conversion(str(html_file), output_dir, sanitized_name)


def try_alternative_conversion(html_file: str, output_dir: str, output_name: str) -> bool:
    """Try alternative methods to convert HTML to DOCX if the primary method fails."""
    _logger.info("\tTrying alternative conversion methods...")

    # Try with different parameters
    try:
        subprocess.run(
            f"libreoffice --headless --convert-to docx {html_file} --outdir {output_dir}",
            check=False,
            shell=True,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        _logger.error("\t\tLibreOffice conversion timed out")

    output_docx = Path(output_dir) / f"{output_name}.docx"
    if output_docx.exists():
        _logger.info(f"\t\tSuccessfully converted to DOCX: {output_docx}")
        return True

    # Try with Pandoc if available
    try:
        subprocess.run(
            f"pandoc -f html -t docx -o {output_docx} {html_file}",
            check=False,
            shell=True,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if Path(output_docx).exists():
            _logger.info(f"\t\tSuccessfully converted to DOCX with Pandoc: {output_docx}")
            return True
    except Exception:
        _logger.exception("\t\tError converting with Pandoc")

    _logger.error("\t\tAll conversion attempts failed.")
    return False


def main() -> None:
    """Run the document conversion utility.

    Converts all DOC files in the 'temp' directory to DOCX format and saves them to the same directory.
    """
    path_dir = "temp"
    output_dir = "temp"

    # Create output directory if it doesn't exist
    Path(output_dir).mkdir(exist_ok=True)

    # Use Path for better file handling
    doc_files = list(Path(path_dir).glob("*.doc"))

    if not doc_files:
        _logger.warning(f"No DOC files found in {path_dir}")
        return

    _logger.info(f"Found {len(doc_files)} DOC files to convert")

    success_count = 0
    for doc_file in doc_files:
        if convert_doc_to_docx(str(doc_file), output_dir):
            success_count += 1

    _logger.info(f"Conversion completed: {success_count}/{len(doc_files)} files successfully converted")


if __name__ == "__main__":
    main()
