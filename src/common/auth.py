"""
Azure authentication module.

Handles authentication to Azure services using Managed Identity or Service Principal.
"""

from typing import Optional

from azure.identity import (
    ChainedTokenCredential,
    DefaultAzureCredential,
    ManagedIdentityCredential,
    ClientSecretCredential,
    AzureCliCredential
)
from azure.core.credentials import TokenCredential

from src.common.config import get_config
from src.common.logging_config import get_logger

logger = get_logger(__name__)


class AzureAuthenticator:
    """Handles Azure authentication."""

    def __init__(self):
        """Initialize Azure authenticator."""
        self.config = get_config()
        self._credential: Optional[TokenCredential] = None

    def get_credential(self) -> TokenCredential:
        """
        Get Azure credential for authentication.

        Returns:
            TokenCredential instance

        Raises:
            ValueError: If authentication fails
        """
        if self._credential is not None:
            return self._credential

        try:
            if self.config.azure.use_managed_identity:
                logger.info("Using Managed Identity for authentication")
                self._credential = self._get_managed_identity_credential()
            else:
                logger.info("Using Service Principal for authentication")
                self._credential = self._get_service_principal_credential()

            # Test the credential
            self._test_credential(self._credential)
            logger.info("Azure authentication successful")
            return self._credential

        except Exception as e:
            logger.error(f"Azure authentication failed: {e}")
            raise ValueError(f"Failed to authenticate with Azure: {e}") from e

    def _get_managed_identity_credential(self) -> TokenCredential:
        """
        Get Managed Identity credential with fallback chain.

        Returns:
            TokenCredential instance
        """
        # Try multiple authentication methods in order
        credentials = [
            ManagedIdentityCredential(),
            AzureCliCredential(),  # Fallback for local development
        ]

        return ChainedTokenCredential(*credentials)

    def _get_service_principal_credential(self) -> TokenCredential:
        """
        Get Service Principal credential.

        Returns:
            ClientSecretCredential instance

        Raises:
            ValueError: If required credentials are missing
        """
        if not self.config.azure.client_id or not self.config.azure.client_secret:
            raise ValueError(
                "Service Principal authentication requires client_id and client_secret"
            )

        return ClientSecretCredential(
            tenant_id=self.config.azure.tenant_id,
            client_id=self.config.azure.client_id,
            client_secret=self.config.azure.client_secret,
        )

    def _test_credential(self, credential: TokenCredential) -> None:
        """
        Test credential by requesting a token.

        Args:
            credential: Credential to test

        Raises:
            Exception: If credential test fails
        """
        try:
            # Request token for Azure Management API
            token = credential.get_token("https://management.azure.com/.default")
            if not token or not token.token:
                raise ValueError("Failed to obtain access token")
        except Exception as e:
            logger.error(f"Credential test failed: {e}")
            raise

    def get_default_credential(self) -> TokenCredential:
        """
        Get default Azure credential (for backward compatibility).

        Returns:
            DefaultAzureCredential instance
        """
        return DefaultAzureCredential()


# Global authenticator instance
_authenticator: Optional[AzureAuthenticator] = None


def get_azure_credential() -> TokenCredential:
    """
    Get Azure credential for authentication.

    Returns:
        TokenCredential instance
    """
    global _authenticator
    if _authenticator is None:
        _authenticator = AzureAuthenticator()
    return _authenticator.get_credential()


def reset_authenticator() -> None:
    """Reset global authenticator instance (useful for testing)."""
    global _authenticator
    _authenticator = None
