from datetime import datetime

from pydantic import BaseModel


class FileMetadata(BaseModel):
    key: str
    filename: str
    folder: str
    size_bytes: int
    size_human: str
    content_type: str
    uploaded_at: datetime
    url: str | None = None


class FileMetadataDetail(BaseModel):
    """Fingerprint-only metadata for the kept /upload reference surface.

    The starter kit shipped image (EXIF) + PDF + audio/video fields here; this
    sample's metadata extractor (app/service/metadata.py) only computes size,
    MIME, extension, MD5, and SHA-256, so the heavier fields were removed from
    both this model and the matching TypeScript shape in packages/shared.
    """

    filename: str
    size_bytes: int
    size_human: str
    mime_type: str
    extension: str
    md5: str
    sha256: str
    uploaded_at: datetime
