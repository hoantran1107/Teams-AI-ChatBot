"""
URL Shortening Service for RAG Citations

Provides functionality to create short URLs for Microsoft URLs only (SharePoint, OneDrive, etc.)
while maintaining the original URL for all other URLs. This improves citation readability
in chat responses without losing functionality.
"""

import re
from urllib.parse import urlparse
from typing import Optional, Tuple
from src.config.settings import url_shortening_domain
from src.services.postgres.models.tables.rag_sync_db.url_shortening_table import (
    URLShortening,
)


class URLShorteningService:
    """Service for managing URL shortening for citations - Microsoft URLs only"""

    def __init__(self):
        self.base_domain = url_shortening_domain

    def shorten_url(self, original_url: str) -> Tuple[str, str]:
        """
        Create or retrieve a short URL for the given original URL
        Only Microsoft URLs (SharePoint, OneDrive, etc.) are shortened.
        All other URLs are returned as-is.

        Args:
            original_url: The full URL to shorten

        Returns:
            Tuple of (short_url, display_url)
            - short_url: The shortened URL for redirection
            - display_url: User-friendly display text for the URL
        """
        # Check if this is a Microsoft URL - only shorten Microsoft URLs
        if not self._is_microsoft_url(original_url):
            # For non-Microsoft URLs, return original URL with formatted display
            display_url = self._format_non_microsoft_display_url(original_url)
            return original_url, display_url

        # Generate display URL for Microsoft URLs
        display_url = self._format_display_url(original_url)

        # Get or create URL mapping in database
        url_mapping = URLShortening.create_or_get_mapping(
            original_url=original_url, display_url=display_url
        )

        # Construct short URL for Microsoft URLs
        short_url = f"{self.base_domain}/redirect/{url_mapping.short_code}"

        return short_url, display_url

    def get_original_url(self, short_code: str) -> Optional[str]:
        """
        Retrieve the original URL for a given short code

        Args:
            short_code: The short code to look up

        Returns:
            Original URL if found, None otherwise
        """
        url_mapping = URLShortening.get_by_short_code(short_code)
        if url_mapping:
            # Record the access for analytics
            url_mapping.record_access()
            return url_mapping.original_url
        return None

    def _is_microsoft_url(self, url: str) -> bool:
        """
        Check if the URL is a Microsoft URL that should be shortened

        Args:
            url: URL to check

        Returns:
            True if this is a Microsoft URL that should be shortened
        """
        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower()

            # Check for Microsoft domains that should be shortened
            microsoft_domains = [
                "sharepoint.com",
                "onedrive.live.com",
                "office.com",
                "microsoft.com",
                "microsoftonline.com",
            ]

            return any(ms_domain in domain for ms_domain in microsoft_domains)

        except Exception:
            return False

    def _format_non_microsoft_display_url(self, url: str) -> str:
        """
        Format non-Microsoft URL for display purposes

        Args:
            url: Original non-Microsoft URL

        Returns:
            Formatted display URL for non-Microsoft URLs
        """
        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower()

            # Handle specific non-Microsoft domains
            if "storage.cloud.google.com" in domain:
                return "GCP Cloud Storage"
            elif "storage.googleapis.com" in domain:
                return "Google Cloud Storage"
            elif "atlassian.net" in domain:
                if "wiki" in parsed_url.path:
                    return f"{domain.split('.')[0]} Confluence"
                else:
                    return f"{domain.split('.')[0]} Atlassian"
            else:
                # Generic formatting for other domains
                return self._format_generic_url(parsed_url)

        except Exception:
            return "Document"

    def _format_display_url(self, url: str) -> str:
        """
        Format Microsoft URL for display purposes (shortened but readable)

        Args:
            url: Original Microsoft URL

        Returns:
            Formatted display URL for Microsoft URLs
        """
        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower()

            # Process Microsoft URLs by domain type
            if "sharepoint.com" in domain:
                return self._format_sharepoint_url(domain)
            elif "onedrive.live.com" in domain:
                return "onedrive.live.com/..."
            elif self._is_microsoft_domain_legacy(domain):
                return f"{domain}/..."
            else:
                return self._format_generic_url(parsed_url)

        except Exception:
            return self._format_fallback_url(url)

    def _format_sharepoint_url(self, domain):
        """Format SharePoint URLs specifically"""
        # Handle Personal SharePoint/OneDrive (organization-my.sharepoint.com)
        match = re.match(r"([^-]+)-my\.sharepoint\.com", domain)
        if match:
            org = match.group(1)
            return f"{org} SharePoint/OneDrive"

        # Handle Team SharePoint sites (organization.sharepoint.com)
        match = re.match(r"([^.]+)\.sharepoint\.com", domain)
        if match:
            org = match.group(1)
            return f"{org} SharePoint"

        # Fallback for any other SharePoint domains
        return f"{domain}/..."

    def _is_microsoft_domain_legacy(self, domain):
        """Check if domain is a Microsoft domain (legacy method for display formatting)"""
        ms_domains = ["office.com", "microsoft.com", "microsoftonline.com"]
        return any(ms_domain in domain for ms_domain in ms_domains)

    def _format_generic_url(self, parsed_url):
        """Format generic URLs with domain and path prefix"""
        domain = parsed_url.netloc
        path_parts = parsed_url.path.strip("/").split("/")

        if path_parts and path_parts[0]:
            return f"{domain}/{path_parts[0]}/..."
        return f"{domain}/..."

    def _format_fallback_url(self, url):
        """Format URL when parsing fails"""
        try:
            domain = urlparse(url).netloc
            return f"{domain}/..." if domain else "document"
        except Exception:
            return "document"


# Global service instance
url_shortening_service = URLShorteningService()
