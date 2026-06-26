import re
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings

# The canonical .env lives at the repo root, but the API is launched from
# `services/api/` (see `pnpm dev:api`). Resolve the root .env by absolute
# path so credentials load regardless of the working directory — otherwise
# settings silently fall back to empty defaults and every external call
# (OpenAI, B2) fails at runtime. A CWD-local `.env`, if present, still wins.
_REPO_ROOT = Path(__file__).resolve().parents[4]
B2_REGION_PLACEHOLDER = "your-b2-region"
B2_ENDPOINT_PLACEHOLDER = "your-b2-endpoint"
B2_REGION_PATTERN = re.compile(r"^[a-z]{2}(?:-[a-z]+)+-[0-9]{3}$")
B2_ENDPOINT_PATTERN = re.compile(
    r"^https://s3\.(?P<region>[a-z]{2}(?:-[a-z]+)+-[0-9]{3})"
    r"\.backblazeb2\.com/?$"
)


class Settings(BaseSettings):
    # Backblaze B2 — canonical names per parent CLAUDE.md.
    # All defaults are intentionally empty: the user supplies real
    # values via .env (see .env.example for the example region/endpoint).
    b2_application_key_id: str = ""
    b2_application_key: str = ""
    b2_bucket_name: str = ""
    b2_region: str = ""
    b2_endpoint: str = ""
    b2_public_url_base: str = ""

    # OpenAI
    openai_api_key: str = ""
    openai_realtime_model: str = "gpt-realtime-2"
    openai_summary_model: str = "gpt-4.1-mini"

    api_port: int = 8000
    # Explicit allowlist by default — covers Next on :3000 and the
    # fallback :3001 it picks if 3000 is busy. Production deploys should
    # override with the exact frontend origin.
    api_cors_origins: str = "http://localhost:3000,http://localhost:3001"
    # Optional dev-only escape hatch: a regex that matches additional
    # allowed origins. Empty by default — set this to e.g.
    # `^http://localhost:\d+$` to accept any localhost port without
    # listing each one. NEVER ship this to production.
    api_cors_origin_regex: str = ""

    # Upload limits (reference upload route still ships with the kit).
    max_file_size: int = 100 * 1024 * 1024  # 100MB

    # Small durable counters (downloads, etc). Point at a persistent
    # volume in production if you care about surviving restarts.
    download_count_file: str = "data/download_count.json"

    # Tuple is loaded in order; a CWD-local `.env` overrides the repo-root one.
    model_config = {
        "env_file": (str(_REPO_ROOT / ".env"), ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @field_validator("b2_region")
    @classmethod
    def validate_b2_region(cls, value: str) -> str:
        value = value.strip()
        if not value:
            return ""
        if value == B2_REGION_PLACEHOLDER:
            return value
        if not B2_REGION_PATTERN.fullmatch(value):
            raise ValueError(
                "B2_REGION must be a Backblaze region slug like "
                "<country>-<region>-<number>"
            )
        return value

    @field_validator("b2_endpoint")
    @classmethod
    def validate_b2_endpoint(cls, value: str) -> str:
        value = value.strip().rstrip("/")
        if not value or value == B2_ENDPOINT_PLACEHOLDER:
            return value
        if not B2_ENDPOINT_PATTERN.fullmatch(value):
            raise ValueError(
                "B2_ENDPOINT must be a Backblaze S3 endpoint like "
                "https://s3.<region>.backblazeb2.com"
            )
        return value

    @property
    def b2_endpoint_url(self) -> str:
        if self.b2_region and self.b2_region != B2_REGION_PLACEHOLDER:
            return f"https://s3.{self.b2_region}.backblazeb2.com"
        if self.b2_endpoint != B2_ENDPOINT_PLACEHOLDER:
            return self.b2_endpoint
        return ""

    @property
    def b2_effective_region(self) -> str:
        if self.b2_region and self.b2_region != B2_REGION_PLACEHOLDER:
            return self.b2_region
        match = B2_ENDPOINT_PATTERN.fullmatch(self.b2_endpoint)
        return match.group("region") if match else ""

    @property
    def uses_legacy_b2_endpoint(self) -> bool:
        return bool(
            self.b2_endpoint
            and self.b2_endpoint != B2_ENDPOINT_PLACEHOLDER
            and not self.b2_region
        )

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",")]


settings = Settings()
