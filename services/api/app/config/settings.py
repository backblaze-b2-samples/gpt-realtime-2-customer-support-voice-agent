from pathlib import Path

from pydantic_settings import BaseSettings

# The canonical .env lives at the repo root, but the API is launched from
# `services/api/` (see `pnpm dev:api`). Resolve the root .env by absolute
# path so credentials load regardless of the working directory — otherwise
# settings silently fall back to empty defaults and every external call
# (OpenAI, B2) fails at runtime. A CWD-local `.env`, if present, still wins.
_REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    # Backblaze B2 — canonical names per parent CLAUDE.md.
    # All defaults are intentionally empty: the user supplies real
    # values via .env (see .env.example for the example region/endpoint).
    b2_endpoint: str = ""
    b2_application_key_id: str = ""
    b2_application_key: str = ""
    b2_bucket_name: str = ""
    b2_region: str = ""
    b2_public_url: str = ""

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
    }

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",")]


settings = Settings()
