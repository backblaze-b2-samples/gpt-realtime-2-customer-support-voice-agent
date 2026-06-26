"""Tests for Backblaze B2 client configuration."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

import main as api_main
from app.config.settings import Settings
from app.repo import b2_client

VALID_B2_REGION = "aa-region-123"
VALID_B2_ENDPOINT = f"https://s3.{VALID_B2_REGION}.backblazeb2.com"


@pytest.fixture(autouse=True)
def reset_s3_client_cache():
    b2_client.clear_s3_client_cache()
    yield
    b2_client.clear_s3_client_cache()


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
    return Settings(
        b2_application_key_id="key-id",
        b2_application_key="key",
        b2_bucket_name="bucket",
        openai_api_key="openai-key",
        **b2_kwargs,
    )


def test_settings_derives_s3_endpoint_from_region():
    settings = _valid_settings(b2_region=VALID_B2_REGION)

    assert settings.b2_endpoint_url == VALID_B2_ENDPOINT
    assert settings.b2_effective_region == VALID_B2_REGION


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
    assert "B2_ENDPOINT is deprecated" in caplog.text


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
