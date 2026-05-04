"""Backblaze B2 state backend settings."""

from __future__ import annotations

from meltano.core.setting_definition import SettingDefinition, SettingKind

APPLICATION_KEY_ID = SettingDefinition(
    name="state_backend.b2.application_key_id",
    label="B2 Application Key ID",
    description="Backblaze B2 Application Key ID used to authenticate",
    kind=SettingKind.STRING,
    sensitive=True,
    env_specific=True,
)

APPLICATION_KEY = SettingDefinition(
    name="state_backend.b2.application_key",
    label="B2 Application Key",
    description="Backblaze B2 Application Key used to authenticate",
    kind=SettingKind.STRING,
    sensitive=True,
    env_specific=True,
)

ENDPOINT_URL = SettingDefinition(
    name="state_backend.b2.endpoint_url",
    label="B2 Endpoint URL",
    description="S3-compatible endpoint URL for the Backblaze B2 region",
    kind=SettingKind.STRING,
    value="https://s3.us-west-004.backblazeb2.com",
    env_specific=True,
)
