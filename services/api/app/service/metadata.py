"""Lightweight metadata for the kept /upload reference route.

The starter kit shipped image (EXIF) + PDF metadata extraction here, but
this sample does not need either — uploads are a reference surface for
seeding documents into the bucket, not the primary capture path. We
trimmed the heavy extractors and now only compute fingerprint metadata
(size, MIME, extension, MD5, SHA-256). See plan §2.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from app.types import FileMetadataDetail
from app.types.formatting import humanize_bytes


def extract_metadata(
    file_data: bytes,
    filename: str,
    content_type: str,
) -> FileMetadataDetail:
    """Compute fingerprint + identity metadata for an uploaded file.

    Intentionally cheap: no PIL, no PyPDF2, no codec sniffing. Content
    type sniffing already happened upstream (UploadFile.content_type +
    extension validation in app/service/upload.py).
    """
    md5 = hashlib.md5(file_data, usedforsecurity=False).hexdigest()
    sha256 = hashlib.sha256(file_data).hexdigest()
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    return FileMetadataDetail(
        filename=filename,
        size_bytes=len(file_data),
        size_human=humanize_bytes(len(file_data)),
        mime_type=content_type,
        extension=extension,
        md5=md5,
        sha256=sha256,
        uploaded_at=datetime.now(UTC),
    )
