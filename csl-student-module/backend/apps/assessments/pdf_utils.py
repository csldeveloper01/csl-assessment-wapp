import hashlib
import os
import re
from typing import Tuple, Dict, Any, Optional
from django.conf import settings
from django.core.exceptions import ValidationError


def sanitize_filename(filename: str) -> str:
    """
    Sanitizes user-provided filename:
    - Strips path traversal sequences (e.g. ../ or \\)
    - Strips control and non-ASCII characters
    - Preserves safe alphanumeric characters, dashes, underscores, and dots
    - Guarantees .pdf extension
    """
    if not filename:
        return "document.pdf"

    # Extract base filename, removing any directory components
    base = os.path.basename(filename.replace("\\", "/"))
    # Remove null bytes and non-printable characters
    base = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", base)
    # Strip dangerous characters
    base = re.sub(r"[^A-Za-z0-9_.\- ]", "_", base).strip()
    
    if not base.lower().endswith(".pdf"):
        base += ".pdf"
        
    return base[:200] if len(base) > 200 else (base or "document.pdf")


def validate_pdf_file(
    file_obj,
    max_size_mb: Optional[int] = None,
) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Strict server-side validation of uploaded PDF question paper:
    1. Validates file existence and non-zero size
    2. Validates maximum file size against configured limit
    3. Validates file extension
    4. Validates PDF magic header (%PDF-)
    5. Validates PDF EOF marker (%%EOF) and parseability
    6. Generates SHA-256 checksum and sanitized metadata
    7. Restores file pointer position
    """
    if not file_obj:
        return False, "No file was uploaded.", {}

    max_mb = max_size_mb or getattr(settings, "MAX_PDF_UPLOAD_SIZE_MB", 10)
    max_bytes = max_mb * 1024 * 1024
    min_bytes = 100  # Smallest conceivable valid PDF structure

    # Check reported or actual size
    file_size = getattr(file_obj, "size", None)

    try:
        current_pos = file_obj.tell() if hasattr(file_obj, "tell") else 0
        file_obj.seek(0)
        content = file_obj.read()
        file_obj.seek(current_pos)
    except Exception as e:
        return False, f"Could not read upload contents: {str(e)}", {}

    actual_size = len(content)
    if actual_size < min_bytes:
        return False, "File is too small or empty to be a valid PDF document.", {}

    if actual_size > max_bytes:
        return (
            False,
            f"File size ({actual_size / (1024 * 1024):.1f} MB) exceeds maximum permitted limit of {max_mb} MB.",
            {},
        )

    # Name check
    original_name = getattr(file_obj, "name", "document.pdf")
    sanitized_name = sanitize_filename(original_name)
    if not original_name.lower().endswith(".pdf"):
        return False, "Uploaded file must have a .pdf extension.", {}

    # Magic byte check (%PDF- must appear in the first 1024 bytes, usually byte 0)
    header = content[:1024]
    if b"%PDF-" not in header:
        return (
            False,
            "Invalid file signature. File does not appear to be a valid PDF document (missing %PDF- header).",
            {},
        )

    # EOF marker check (%%EOF should appear in the last 2048 bytes)
    footer = content[-2048:]
    if b"%%EOF" not in footer:
        return (
            False,
            "Corrupt or malformed PDF: Missing end-of-file (%%EOF) marker.",
            {},
        )

    # Basic structural check: look for object or cross-reference indicators
    has_structure = (
        b"obj" in content or
        b"xref" in content or
        b"startxref" in content or
        b"/Root" in content
    )
    if not has_structure:
        return (
            False,
            "Malformed PDF document: Document lacks recognizable internal PDF object catalog or xref.",
            {},
        )

    # Compute SHA-256 checksum
    sha256 = hashlib.sha256(content).hexdigest()

    metadata = {
        "file_size": actual_size,
        "sha256": sha256,
        "original_filename": sanitized_name,
        "content_type": getattr(file_obj, "content_type", "application/pdf") or "application/pdf",
        "raw_bytes": content,
    }

    return True, None, metadata
