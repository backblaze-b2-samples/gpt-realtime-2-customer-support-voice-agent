"""Tests for Backblaze B2 client configuration."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

import main as api_main
from app.config.settings import (
    B2_ENDPOINT_PATTERN,
    B2_ENDPOINT_PLACEHOLDER,
    B2_REGION_PATTERN,
    B2_REGION_PLACEHOLDER,
    Settings,
)
from app.repo import b2_client

VALID_B2_REGION = "aa-region-123"
VALID_B2_ENDPOINT = f"https://s3.{VALID_B2_REGION}.backblazeb2.com"
REPO_ROOT = Path(__file__).resolve().parents[3]


def _clear_s3_client_cache() -> None:
    b2_client.get_s3_client.cache_clear()


@pytest.fixture(autouse=True)
def reset_s3_client_cache():
    _clear_s3_client_cache()
    yield
    _clear_s3_client_cache()


def _set_b2_settings(
    monkeypatch,
    *,
    region: str = VALID_B2_REGION,
    endpoint: str = "",
    public_url_base: str = "",
) -> None:
    monkeypatch.setattr(b2_client.settings, "b2_region", region)
    monkeypatch.setattr(b2_client.settings, "b2_endpoint", endpoint)
    monkeypatch.setattr(b2_client.settings, "b2_public_url_base", public_url_base)
    monkeypatch.setattr(b2_client.settings, "b2_application_key_id", "key-id")
    monkeypatch.setattr(b2_client.settings, "b2_application_key", "key")
    monkeypatch.setattr(b2_client.settings, "b2_bucket_name", "bucket")


def _valid_settings(**b2_kwargs) -> Settings:
    values = {
        "b2_application_key_id": "key-id",
        "b2_application_key": "key",
        "b2_bucket_name": "bucket",
        "b2_region": "",
        "b2_endpoint": "",
        "openai_api_key": "openai-key",
    }
    values.update(b2_kwargs)
    return Settings(_env_file=None, **values)


def test_b2_config_contract_stays_in_sync():
    env_example = (REPO_ROOT / ".env.example").read_text()
    doctor = (REPO_ROOT / "scripts/doctor.mjs").read_text()

    required_b2_names = {
        env_name for _attr, env_name in api_main.REQUIRED_B2_SETTINGS
    }
    endpoint_names = {
        env_name for _attr, env_name in api_main.B2_ENDPOINT_SETTINGS
    }

    assert required_b2_names == {
        "B2_APPLICATION_KEY_ID",
        "B2_APPLICATION_KEY",
        "B2_BUCKET_NAME",
    }
    assert endpoint_names == {"B2_REGION", "B2_ENDPOINT"}
    assert "B2_PUBLIC_URL_BASE=" in env_example
    for name in required_b2_names | endpoint_names:
        assert name in env_example
        assert name in doctor

    for placeholder in (B2_REGION_PLACEHOLDER, B2_ENDPOINT_PLACEHOLDER):
        assert placeholder in api_main.PLACEHOLDER_VALUES
        assert placeholder in env_example
        assert placeholder in doctor

    assert B2_REGION_PATTERN.pattern in doctor
    assert B2_ENDPOINT_PATTERN.fullmatch(VALID_B2_ENDPOINT)
    assert "backblazeb2\\.com" in doctor


def test_settings_derives_s3_endpoint_from_region():
    settings = _valid_settings(b2_region=VALID_B2_REGION)

    assert settings.b2_endpoint_url == VALID_B2_ENDPOINT
    assert settings.b2_effective_region == VALID_B2_REGION


@pytest.mark.parametrize(
    "b2_kwargs",
    [
        {"b2_region": B2_REGION_PLACEHOLDER},
        {"b2_endpoint": B2_ENDPOINT_PLACEHOLDER},
    ],
)
def test_settings_allows_b2_placeholders_for_startup_guidance(b2_kwargs):
    settings = _valid_settings(**b2_kwargs)

    assert settings.b2_endpoint_url == ""
    assert settings.b2_effective_region == ""


@pytest.mark.parametrize(
    "region",
    [
        f"https://s3.{VALID_B2_REGION}.backblazeb2.com",
        f"{VALID_B2_REGION}@example.com",
        "aa/region/123",
        "aa.region.123",
        "aa region 123",
        f"{VALID_B2_REGION}:443",
    ],
)
def test_settings_rejects_invalid_b2_region(region):
    with pytest.raises(ValidationError, match="B2_REGION"):
        _valid_settings(b2_region=region)


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://example.com",
        "http://s3.aa-region-123.backblazeb2.com",
        "https://s3.aa.region.123.backblazeb2.com",
    ],
)
def test_settings_rejects_invalid_legacy_b2_endpoint(endpoint):
    with pytest.raises(ValidationError, match="B2_ENDPOINT"):
        _valid_settings(b2_endpoint=endpoint)


def test_public_url_base_is_used_in_listed_file_metadata(monkeypatch):
    class FakeS3Client:
        def list_objects_v2(self, **_kwargs):
            return {
                "Contents": [
                    {
                        "Key": "folder/a file.txt",
                        "Size": 12,
                        "LastModified": datetime(2026, 1, 1, tzinfo=UTC),
                    }
                ]
            }

    _set_b2_settings(
        monkeypatch,
        public_url_base="https://f004.backblazeb2.com/file/example-bucket/",
    )
    monkeypatch.setattr(
        b2_client.boto3,
        "client",
        lambda _service_name, **_kwargs: FakeS3Client(),
    )

    files = b2_client.list_files()

    assert len(files) == 1
    assert (
        files[0].url
        == "https://f004.backblazeb2.com/file/example-bucket/folder/a%20file.txt"
    )


def test_s3_client_uses_region_endpoint_and_sample_user_agent(monkeypatch):
    captured = {}

    def fake_client(service_name, **kwargs):
        captured["service_name"] = service_name
        captured.update(kwargs)
        return object()

    _set_b2_settings(monkeypatch)
    monkeypatch.setattr(b2_client.boto3, "client", fake_client)

    b2_client.get_s3_client()

    assert captured["service_name"] == "s3"
    assert captured["endpoint_url"] == VALID_B2_ENDPOINT
    assert captured["region_name"] == VALID_B2_REGION
    assert captured["config"].user_agent_extra.endswith("(backblaze-b2-samples)")


def test_s3_client_falls_back_to_legacy_endpoint(monkeypatch, caplog):
    captured = {}

    def fake_client(service_name, **kwargs):
        captured["service_name"] = service_name
        captured.update(kwargs)
        return object()

    _set_b2_settings(monkeypatch, region="", endpoint=VALID_B2_ENDPOINT)
    monkeypatch.setattr(b2_client.boto3, "client", fake_client)

    b2_client.get_s3_client()

    assert captured["endpoint_url"] == VALID_B2_ENDPOINT
    assert captured["region_name"] == VALID_B2_REGION
    assert "B2_ENDPOINT is deprecated" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "b2_kwargs",
    [
        {"b2_region": VALID_B2_REGION},
        {"b2_endpoint": VALID_B2_ENDPOINT},
    ],
)
async def test_startup_accepts_region_or_legacy_endpoint(monkeypatch, b2_kwargs):
    monkeypatch.setattr(api_main, "settings", _valid_settings(**b2_kwargs))

    async with api_main.lifespan(None):
        pass


@pytest.mark.asyncio
async def test_startup_requires_region_or_legacy_endpoint(monkeypatch):
    monkeypatch.setattr(api_main, "settings", _valid_settings())

    with pytest.raises(RuntimeError, match="B2_REGION"):
        async with api_main.lifespan(None):
            pass


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("b2_kwargs", "env_name"),
    [
        ({"b2_region": B2_REGION_PLACEHOLDER}, "B2_REGION"),
        ({"b2_endpoint": B2_ENDPOINT_PLACEHOLDER}, "B2_ENDPOINT"),
    ],
)
async def test_startup_reports_b2_placeholders(monkeypatch, b2_kwargs, env_name):
    monkeypatch.setattr(api_main, "settings", _valid_settings(**b2_kwargs))

    with pytest.raises(RuntimeError, match=env_name):
        async with api_main.lifespan(None):
            pass
