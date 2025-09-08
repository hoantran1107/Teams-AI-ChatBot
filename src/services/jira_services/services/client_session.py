from typing import Any

import aiohttp


class ClientSession:
    """Asynchronous HTTP client session wrapper using aiohttp.

    This class provides an async context-managed session and a helper
    for GET requests returning JSON responses.
    """

    def __init__(self, headers: dict, auth: aiohttp.BasicAuth | None = None):
        """Initialize the client session.

        Args:
            headers (dict): HTTP headers to include in all requests.
            auth (aiohttp.BasicAuth, optional): Basic authentication credentials.

        """
        self.headers = headers
        self.auth = auth
        self.session = None

    async def __aenter__(self):
        """Enter the asynchronous context and initialize the aiohttp session.

        Returns:
            ClientSession: This instance with an active session.

        """
        self.session = aiohttp.ClientSession(headers=self.headers, auth=self.auth)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the asynchronous context and close the aiohttp session.

        Args:
            exc_type: Exception type if raised.
            exc_val: Exception value if raised.
            exc_tb: Traceback if exception raised.

        """
        if self.session:
            await self.session.close()

    async def get_json(self, url: str, params: dict | None = None) -> Any | None:
        """Perform a GET request and return the JSON response.

        Args:
            url (str): The full URL to request.
            params (dict, optional): Query parameters for the request.

        Returns:
            dict | None: JSON response if status is 200, otherwise None.

        """
        async with self.session.get(url, params=params) as response:
            if response.status == 200:
                return await response.json()
            return None

    async def post_json(self, url: str, data: dict) -> dict | None:
        """Perform a POST request and return the JSON response.

        Args:
            url (str): The full URL to request.
            data (dict): Data to send in the request body.

        Returns:
            dict | None: JSON response if status is 201, otherwise None.

        """
        async with self.session.post(url, json=data) as response:
            if response.status == 201:
                return await response.json()
            return None
