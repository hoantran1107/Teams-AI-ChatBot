from collections.abc import Callable
from typing import TypeVar

from google.cloud.secretmanager import (
    AccessSecretVersionRequest,
    SecretManagerServiceClient,
)
from google.oauth2 import service_account

from src.config.environment import env

# Type variable for the return type of access_value
T = TypeVar("T")


class GoogleConfig:
    """Configuration for Google Cloud Services.

    Contains constants for Google Cloud APIs and services.
    """

    GEOCODE_API_URL = "https://maps.googleapis.com/maps/api/geocode/json"
    GCLOUD_PROJECT_ID = "ifd-cpb-prod"


_secret_manger: SecretManagerServiceClient | None = None


def open_secret_client(cred: service_account.Credentials) -> None:
    """Initialize the secret manager client with credentials.

    Args:
        cred: Google service account credentials.

    """
    global _secret_manger

    _secret_manger = SecretManagerServiceClient(credentials=cred)


def access_value[T](output: Callable[[str], T], secret: str, version: str = "latest") -> T:
    """Access and retrieve a secret value from Secret Manager.

    Args:
        output: Function to convert the secret value to desired data type.
        secret: Name of the secret to retrieve.
        version: Version of the secret, defaults to "latest".

    Returns:
        The secret value converted to the type specified by the output function.

    """
    request = AccessSecretVersionRequest(
        name=f"projects/{env.get_str(key='GCLOUD_PROJECT_ID')}/secrets/{secret}/versions/" + version,
    )

    payload = _secret_manger.access_secret_version(request=request).payload

    out = payload.data.decode("utf-8")

    return output(out)


def close_secret_client() -> None:
    """Close the secret manager client connection.

    Should be called when done using the secret manager to free resources.
    """
    if _secret_manger:
        _secret_manger.transport.close()
