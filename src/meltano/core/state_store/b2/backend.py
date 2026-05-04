"""StateStoreManager for Backblaze B2 cloud storage backend."""

from __future__ import annotations

import os
import typing as t
from functools import cached_property

import boto3

from meltano.core.error import MeltanoError
from meltano.core.state_store.filesystem import (
    InvalidStateBackendConfigurationException,
)
from meltano.core.state_store.s3.backend import S3StateStoreManager

if t.TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client


DEFAULT_B2_ENDPOINT_URL = "https://s3.us-west-004.backblazeb2.com"
B2_APPLICATION_KEY_ID_ENV_VAR = "B2_APPLICATION_KEY_ID"
B2_APPLICATION_KEY_ENV_VAR = "B2_APPLICATION_KEY"
B2_ENDPOINT_URL_ENV_VAR = "B2_ENDPOINT_URL"


class B2AuthenticationError(MeltanoError):
    """Backblaze B2 credentials were missing or incomplete."""


class B2StateStoreManager(S3StateStoreManager):
    """State backend for Backblaze B2 (S3-compatible)."""

    label: str = "Backblaze B2"

    def __init__(
        self,
        application_key_id: str | None = None,
        application_key: str | None = None,
        bucket: str | None = None,
        prefix: str | None = None,
        endpoint_url: str | None = None,
        **kwargs: t.Any,
    ):
        """Initialize the B2StateStoreManager.

        Args:
            application_key_id: B2 Application Key ID used to authenticate
            application_key: B2 Application Key used to authenticate
            bucket: the bucket to store state in
            prefix: the prefix to store state at
            endpoint_url: the S3-compatible endpoint url for B2
            kwargs: additional keyword args to pass to parent
        """
        if application_key_id is None:
            application_key_id = os.environ.get(B2_APPLICATION_KEY_ID_ENV_VAR)
        if application_key is None:
            application_key = os.environ.get(B2_APPLICATION_KEY_ENV_VAR)
        if endpoint_url is None:
            endpoint_url = os.environ.get(B2_ENDPOINT_URL_ENV_VAR)

        super().__init__(
            aws_access_key_id=application_key_id,
            aws_secret_access_key=application_key,
            bucket=bucket,
            prefix=prefix,
            endpoint_url=endpoint_url or DEFAULT_B2_ENDPOINT_URL,
            **kwargs,
        )

    @cached_property
    def client(self) -> S3Client:
        """Get an authenticated boto3.Client.

        Returns:
            A boto3.Client.

        Raises:
            InvalidStateBackendConfigurationException: when only one half
                of the B2 credential pair is provided.
            B2AuthenticationError: when no B2 credentials are configured.
        """
        if self.aws_secret_access_key and self.aws_access_key_id:
            session = boto3.Session(
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
            )
            return session.client("s3", endpoint_url=self.endpoint_url)
        if self.aws_secret_access_key:
            raise InvalidStateBackendConfigurationException(  # noqa: TRY003
                "B2 application key configured, but no B2 application key ID.",  # noqa: EM101
            )
        if self.aws_access_key_id:
            raise InvalidStateBackendConfigurationException(  # noqa: TRY003
                "B2 application key ID configured, but no B2 application key.",  # noqa: EM101
            )
        raise B2AuthenticationError(
            reason="No Backblaze B2 credentials configured",
            instruction=(
                "Set state_backend.b2.application_key_id and "
                "state_backend.b2.application_key (or the equivalent env "
                "vars) to a bucket-scoped B2 Application Key"
            ),
        )
