"""Tests for Backblaze B2 client configuration."""

from app.config.settings import Settings
from app.repo import b2_client


def test_settings_derives_s3_endpoint_from_region():
    settings = Settings(
        b2_application_key_id="key-id",
        b2_application_key="key",
        b2_bucket_name="bucket",
        b2_region="test-region",
    )

    assert settings.b2_endpoint_url == "https://s3.test-region.backblazeb2.com"


def test_public_url_uses_standard_base(monkeypatch):
    monkeypatch.setattr(
        b2_client.settings,
        "b2_public_url_base",
        "https://f004.backblazeb2.com/file/example-bucket/",
    )

    assert (
        b2_client._public_url("folder/a file.txt")
        == "https://f004.backblazeb2.com/file/example-bucket/folder/a%20file.txt"
    )


def test_s3_client_uses_backblaze_sample_user_agent(monkeypatch):
    captured = {}

    def fake_client(service_name, **kwargs):
        captured["service_name"] = service_name
        captured.update(kwargs)
        return object()

    b2_client.get_s3_client.cache_clear()
    monkeypatch.setattr(b2_client.boto3, "client", fake_client)
    monkeypatch.setattr(b2_client.settings, "b2_region", "test-region")
    monkeypatch.setattr(b2_client.settings, "b2_application_key_id", "key-id")
    monkeypatch.setattr(b2_client.settings, "b2_application_key", "key")

    b2_client.get_s3_client()

    assert captured["service_name"] == "s3"
    assert captured["endpoint_url"] == "https://s3.test-region.backblazeb2.com"
    assert captured["config"].user_agent_extra.endswith("(backblaze-b2-samples)")

    b2_client.get_s3_client.cache_clear()
