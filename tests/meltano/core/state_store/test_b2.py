"""Tests for the Backblaze B2 state backend."""

from __future__ import annotations

import json

import moto
import pytest

from meltano.core.state_store import MeltanoState
from meltano.core.state_store.b2.backend import (
    DEFAULT_B2_ENDPOINT_URL,
    B2AuthenticationError,
    B2StateStoreManager,
)
from meltano.core.state_store.filesystem import (
    InvalidStateBackendConfigurationException,
)


class TestB2StateStoreManager:
    @pytest.fixture(autouse=True)
    def clean_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # moto5 requires a default region; pin one rather than deleting it.
        monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
        monkeypatch.delenv("AWS_PROFILE", raising=False)
        monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
        monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)

    @pytest.fixture
    def bucket(self) -> str:
        return "some-b2-bucket"

    @pytest.fixture
    def prefix(self) -> str:
        return "state"

    @pytest.fixture
    def application_key_id(self) -> str:
        # AWS docs example access key — moto5 validates the format strictly.
        return "AKIAIOSFODNN7EXAMPLE"

    @pytest.fixture
    def application_key(self) -> str:
        return "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"

    @pytest.fixture
    def subject(
        self,
        bucket: str,
        prefix: str,
        application_key_id: str,
        application_key: str,
    ) -> B2StateStoreManager:
        return B2StateStoreManager(
            uri=f"s3://{bucket}/{prefix}",
            application_key_id=application_key_id,
            application_key=application_key,
            lock_timeout_seconds=10,
        )

    def test_default_endpoint_url(self, subject: B2StateStoreManager) -> None:
        assert subject.endpoint_url == DEFAULT_B2_ENDPOINT_URL

    def test_user_endpoint_url_overrides_default(
        self,
        bucket: str,
        prefix: str,
        application_key_id: str,
        application_key: str,
    ) -> None:
        custom_endpoint = "https://s3.us-east-005.backblazeb2.com"
        manager = B2StateStoreManager(
            uri=f"s3://{bucket}/{prefix}",
            application_key_id=application_key_id,
            application_key=application_key,
            endpoint_url=custom_endpoint,
            lock_timeout_seconds=10,
        )
        assert manager.endpoint_url == custom_endpoint

    def test_b2_credentials_map_to_aws_fields(
        self,
        subject: B2StateStoreManager,
        application_key_id: str,
        application_key: str,
    ) -> None:
        assert subject.aws_access_key_id == application_key_id
        assert subject.aws_secret_access_key == application_key

    def test_b2_env_vars_populate_credentials(
        self,
        bucket: str,
        prefix: str,
        application_key_id: str,
        application_key: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("B2_APPLICATION_KEY_ID", application_key_id)
        monkeypatch.setenv("B2_APPLICATION_KEY", application_key)

        manager = B2StateStoreManager(
            uri=f"s3://{bucket}/{prefix}",
            lock_timeout_seconds=10,
        )

        assert manager.aws_access_key_id == application_key_id
        assert manager.aws_secret_access_key == application_key

    def test_explicit_kwargs_win_over_b2_env_vars(
        self,
        bucket: str,
        prefix: str,
        application_key_id: str,
        application_key: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("B2_APPLICATION_KEY_ID", "AKIAFROM_ENVNOTUSED1")
        monkeypatch.setenv("B2_APPLICATION_KEY", "from-env-not-used")

        manager = B2StateStoreManager(
            uri=f"s3://{bucket}/{prefix}",
            application_key_id=application_key_id,
            application_key=application_key,
            lock_timeout_seconds=10,
        )

        assert manager.aws_access_key_id == application_key_id
        assert manager.aws_secret_access_key == application_key

    def test_b2_endpoint_url_env_var_is_honored(
        self,
        bucket: str,
        prefix: str,
        application_key_id: str,
        application_key: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        eu_endpoint = "https://s3.eu-central-003.backblazeb2.com"
        monkeypatch.setenv("B2_ENDPOINT_URL", eu_endpoint)

        manager = B2StateStoreManager(
            uri=f"s3://{bucket}/{prefix}",
            application_key_id=application_key_id,
            application_key=application_key,
            lock_timeout_seconds=10,
        )

        assert manager.endpoint_url == eu_endpoint

    def test_label(self) -> None:
        assert B2StateStoreManager.label == "Backblaze B2"

    def test_client_built_with_b2_endpoint_and_credentials(
        self,
        subject: B2StateStoreManager,
        application_key_id: str,
        application_key: str,
    ) -> None:
        client = subject.client
        assert client.meta.endpoint_url == DEFAULT_B2_ENDPOINT_URL
        creds = client._request_signer._credentials
        assert creds.access_key == application_key_id
        assert creds.secret_key == application_key

    def test_missing_credentials_raises_b2_auth_error(
        self,
        bucket: str,
        prefix: str,
    ) -> None:
        manager = B2StateStoreManager(
            uri=f"s3://{bucket}/{prefix}",
            application_key_id=None,
            application_key=None,
            lock_timeout_seconds=10,
        )

        with pytest.raises(B2AuthenticationError) as exc_info:
            _ = manager.client

        assert "Backblaze B2" in str(exc_info.value)

    def test_partial_credentials_raises_configuration_error(
        self,
        bucket: str,
        prefix: str,
        application_key_id: str,
    ) -> None:
        manager = B2StateStoreManager(
            uri=f"s3://{bucket}/{prefix}",
            application_key_id=application_key_id,
            application_key=None,
            lock_timeout_seconds=10,
        )

        with pytest.raises(
            InvalidStateBackendConfigurationException,
            match="application key",
        ):
            _ = manager.client

    def test_set_and_get_round_trip(
        self,
        bucket: str,
        prefix: str,
        application_key_id: str,
        application_key: str,
    ) -> None:
        state_id = "test_b2_round_trip"
        with moto.mock_aws():
            manager = B2StateStoreManager(
                uri=f"s3://{bucket}/{prefix}",
                application_key_id=application_key_id,
                application_key=application_key,
                lock_timeout_seconds=10,
            )
            manager.client.create_bucket(Bucket=manager.bucket)
            manager.set(MeltanoState(state_id=state_id, completed_state={}))

            obj = manager.client.get_object(
                Bucket=manager.bucket,
                Key=f"{prefix}/{state_id}/state.json",
            )
            assert json.loads(obj["Body"].read())["completed_state"] == {}
