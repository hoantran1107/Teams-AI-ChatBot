import asyncio
import hashlib
import logging
import os

import aiofiles
import aiohttp
import requests
from aiohttp import BasicAuth
from atlassian import Confluence
from requests import RequestException
from requests.auth import HTTPBasicAuth
from sqlalchemy.orm import Session

from src.config.database_config import db as db_interface
from src.config.settings import (
    atlassian_api_token,
    atlassian_confluence_url,
    atlassian_user,
)
from src.constants.app_constants import MIME_TYPE
from src.services.confluence_service.models.api_model import ConfluenceApiResponse
from src.services.confluence_service.models.cql_api_model import ConfluenceCQLInstance
from src.services.cronjob.models.source_handler import DocumentMetadata
from src.services.postgres.models.tables.rag_sync_db.cronjob_log import CronJobLog
from src.services.postgres.models.tables.rag_sync_db.rag_doc_log_table import (
    Collection,
    DocumentLog,
    SourceType,
    SyncLog,
)
from src.utils.file_helper import convert_doc_to_docx_in_folder

_logger = logging.getLogger("ConfluenceService")


class ConfluenceService:
    def __init__(
        self,
        base_url=atlassian_confluence_url,
        collection_id=None,
        username=atlassian_user,
        api_token=atlassian_api_token,
    ):
        self.collection_id = collection_id or 0
        self.base_url = base_url
        self.auth = HTTPBasicAuth(username, api_token)
        self.aio_auth = BasicAuth(username, api_token)
        self.headers = {"Accept": MIME_TYPE}
        self.confluence = Confluence(
            url=base_url,
            username=atlassian_user,
            password=atlassian_api_token,
            api_version="cloud",
        )

    async def add_confluence_page(
        self,
        page_id,
        collection_id: int,
        enable_child_pages: bool = False,
        pages_child_id: list[str] | None = None,
        db_session: Session | None = None,
        called_from_gui: bool = True,
    ):
        db_to_use = db_session or db_interface.session
        collection = self._get_collection(collection_id, db_to_use)

        if not collection:
            raise ValueError(f"Collection {collection_id} does not exist, please refresh the page and try again")

        if isinstance(collection, list):
            collection = collection[0]

        collection_id = collection.id
        collection_name = collection.name

        success_ids, failed_ids = await self._add_pages(
            main_page_id=page_id,
            collection_id=collection_id,
            db_session=db_to_use,
            child_ids=pages_child_id,
        )

        if called_from_gui:
            self._handle_gui_errors(success_ids, failed_ids)

        _logger.info(
            f"Added pages {success_ids} to collection {collection.name} with ID {collection_id} and error pages {failed_ids}",
        )
        return {"collection_name": collection_name}

    def _get_collection(self, id_: int, db: Session):
        return Collection.find_by_filter(id=id_, db_session=db)

    async def _add_pages(self, main_page_id, child_ids, collection_id, db_session):
        success_ids, failed_ids = [], []

        async def try_add_page(pid):
            if DocumentLog.find_by_filter(
                identity_constant_name=pid,
                collection_id=collection_id,
                source_type=SourceType.CONFLUENCE,
            ):
                failed_ids.append(pid)
                return

            page_model = await self.get_version_history_and_create_page(
                page_id=pid,
                collection_id=collection_id,
                db_to_use=db_session,
            )
            if page_model:
                success_ids.append(pid)

        await try_add_page(main_page_id)
        for pid in child_ids:
            await try_add_page(pid)

        return success_ids, failed_ids

    def _handle_gui_errors(self, success_ids, failed_ids):
        if not success_ids and failed_ids:
            raise ValueError(f"Some pages already exist: {failed_ids}")
        if success_ids and failed_ids:
            raise ValueError(
                f"Some pages were added successfully: {success_ids}, but some pages already exist: {failed_ids}",
            )

    async def get_version_history_and_create_page(self, page_id, collection_id, db_to_use) -> dict | None:
        page_model = await self.get_version_history_async(page_id)
        if not page_model:
            return None

        return DocumentLog.create(
            identity_constant_name=page_model.page_id,
            display_name=page_model.page_name,
            version=page_model.version,
            created_date=page_model.created_date,
            updated_date=page_model.updated_date,
            source_created_date=page_model.created_date,
            source_updated_date=page_model.updated_date,
            collection_id=collection_id,
            db_session=db_to_use,
            source_type=SourceType.CONFLUENCE,
            source_path=atlassian_confluence_url,
            is_new_doc=True,
            url_download=f"{atlassian_confluence_url}/pages/viewpage.action?pageId={page_model.page_id}",
        ).to_dict()

    async def get_version_history_async(self, page_id: str) -> ConfluenceApiResponse | None:
        """Get the version history and create a page model.

        Args:
            page_id: The ID of the page to get the version history for

        Returns:
            ConfluenceApiResponse | None: The page model if successful, None otherwise

        """
        url = f"{self.base_url}/rest/api/content/{page_id}?expand=version,history"
        retry = 3
        for _ in range(retry):
            async with (
                aiohttp.ClientSession() as session,
                session.get(url, headers=self.headers, auth=self.aio_auth) as response,
            ):
                if response.status == 200:
                    return ConfluenceApiResponse.from_api_response(await response.json())
                if response.status == 404:
                    _logger.error("Page with ID %s not found.", page_id)
                    return None
                if response.status == 429:
                    _logger.warning("Rate limited (429) for page ID %s, retrying %s of %s...", page_id, _ + 1, retry)
                    await asyncio.sleep(2 ** (_ + 1))  # Exponential backoff
                else:
                    _logger.error("Failed to get page content: %s - %s", response.status, response.text)
                    return None
        return None

    async def export_to_doc_file(self, file_new, folder_path) -> str | None:
        """Export a Confluence page to a Word document file.

        Args:
            file_new: Object containing page_id and page_name
            folder_path: Directory path where the file will be saved

        Returns:
            str | None: Path to the exported file if successful, None otherwise

        """
        url = f"{self.base_url}/exportword?pageId={file_new.page_id}"
        max_retries = 3

        # Try to download the file with retry logic
        response_content = await self._download_file_with_retry(url, file_new.page_id, max_retries)
        if response_content is None:
            return None

        # Save the file to disk
        return await self._save_file_to_disk(response_content, file_new.page_name, folder_path)

    async def _download_file_with_retry(self, url: str, page_id: str, max_retries: int) -> bytes | None:
        """Download file content with retry logic and exponential backoff.

        Args:
            url: The URL to download from
            page_id: Page ID for logging purposes
            max_retries: Maximum number of retry attempts

        Returns:
            bytes | None: File content if successful, None otherwise

        """
        for attempt in range(max_retries):
            try:
                async with (
                    aiohttp.ClientSession() as session,
                    session.get(url, headers=self.headers, auth=self.aio_auth) as response,
                ):
                    if response.status == 200:
                        return await response.read()

                    if response.status == 429:
                        wait_time = 2 ** (attempt + 1)  # Exponential backoff
                        _logger.warning(
                            "Rate limited (429) for page ID %s, retrying %s of %s... (waiting %s seconds)",
                            page_id,
                            attempt + 1,
                            max_retries,
                            wait_time,
                        )
                        await asyncio.sleep(wait_time)
                        continue

                    # For other error status codes
                    error_text = await response.text()
                    _logger.error("Failed to export page to docx: %s - %s", response.status, error_text)
                    return None

            except aiohttp.ClientError as e:
                _logger.error("Network error downloading file for page %s: %s", page_id, str(e))
                if attempt == max_retries - 1:
                    return None
                await asyncio.sleep(2 ** (attempt + 1))

        return None

    async def _save_file_to_disk(self, content: bytes, page_name: str, folder_path: str) -> str:
        """Save file content to disk.

        Args:
            content: File content as bytes
            page_name: Name of the page (used for filename)
            folder_path: Directory to save the file

        Returns:
            str: Path to the saved file

        """
        # Ensure the directory exists
        os.makedirs(folder_path, exist_ok=True)

        # Create the file path
        file_path_doc = os.path.join(folder_path, f"{page_name}.doc")

        # Write the file asynchronously
        async with aiofiles.open(file_path_doc, "wb") as file:
            await file.write(content)

        _logger.info("Successfully exported page '%s' to %s", page_name, file_path_doc)
        return file_path_doc

    def get_confluence_page(self, page_id):
        url = f"{self.base_url}/rest/api/content/{page_id}"
        response = requests.get(url, headers=self.headers, auth=self.auth)
        return response

    async def get_changes_pages(self, save_to_dir: str) -> dict[str, list[DocumentMetadata]]:
        all_pages = DocumentLog.get_by_collection_and_source(
            collection_id=self.collection_id,
            source_type=SourceType.CONFLUENCE,
            source_path=self.base_url,
        )
        all_pages_dict = self.__get_confluence_pages_has_changes(all_pages)
        all_pages = [*all_pages_dict["news"], *all_pages_dict["updates"]]
        if not all_pages:
            return {
                "news": [],
                "updates": [],
                "deletes": [],
            }

        # download all pages
        await self.download_files_async(list(map(lambda x: x.identity_constant_name, all_pages)), save_to_dir)

        file_maps = convert_doc_to_docx_in_folder(save_to_dir)
        results = dict(news=[], updates=[], deletes=[])
        for type_change in all_pages_dict.keys():
            for page in all_pages_dict[type_change]:
                version = page.version
                display_name = page.display_name
                history_model = await self.get_version_history_async(page.identity_constant_name)
                if not history_model:
                    _logger.warning("Failed to get version history for page %s", page.identity_constant_name)
                    continue

                if type_change == "updates":
                    need_updated = (
                        str(page.version) != str(history_model.version)
                        and page.source_updated_date != history_model.updated_date
                    )
                    if not need_updated:
                        continue
                    version = history_model.version
                    display_name = history_model.page_name
                    page.source_updated_date = history_model.updated_date

                downloaded_path = file_maps.get(page.identity_constant_name, None)
                if downloaded_path:
                    with open(downloaded_path, "rb") as f:
                        content_bytes = f.read()
                    results[type_change].append(
                        DocumentMetadata(
                            db_instance=page,
                            identity_constant_name=page.identity_constant_name,
                            display_name=display_name,
                            size=len(content_bytes),
                            content_type=None,
                            version=str(version),
                            content_hash=hashlib.md5(content_bytes).hexdigest(),
                            download_url=downloaded_path,
                            source_metadata=dict(
                                public_url=f"{self.base_url}/pages/viewpage.action?pageId={page.identity_constant_name}",
                                time_created=page.created_date,
                                updated=page.updated_date,
                                source_type=SourceType.CONFLUENCE,
                                source_path=self.base_url,
                                contents=content_bytes,
                                downloaded_path=downloaded_path,
                            ),
                        ),
                    )

        return results

    def __get_confluence_pages_has_changes(self, all_pages: list[DocumentLog]):
        # First, we split the list into 2 groups: group one contains all new pages, group two contains others.
        # convert all pages to DocumentMetadata
        new_groups = []
        others = []
        for page in all_pages:
            if page.is_new_doc:
                new_groups.append(page)
            else:
                others.append(page)

        cron_job_range_time = CronJobLog.get_minute_range_latest_update(
            collection_id=self.collection_id,
        )
        sync_log_range_time = SyncLog.get_minute_range_latest_update(
            collection_id=self.collection_id,
            source_type=SourceType.CONFLUENCE,
            source_path=self.base_url,
        )
        minute_time_range: int | None
        if cron_job_range_time and sync_log_range_time:
            minute_time_range = min(cron_job_range_time, sync_log_range_time)
        else:
            minute_time_range = cron_job_range_time or sync_log_range_time
        minute_time_range = max(minute_time_range, 1) if minute_time_range else 1
        if minute_time_range:
            # For others, filter in all page_id that has changes in cron_job_range_time minutes
            filtered_others = self.confluence_api_check_page_id_by_cql(
                [item.identity_constant_name for item in others],
                minute_time_range,
            )
            filtered_others = [item for item in others if item.identity_constant_name in filtered_others]
            others = filtered_others if filtered_others else []

        return dict(news=new_groups, updates=others, deletes=[])

    async def download_file_async(self, session, page_id, save_path_dir: str):
        url = f"{self.base_url}/exportword?pageId={page_id}"
        try:
            async with session.get(url, headers=self.headers, auth=self.aio_auth) as response:
                if response.status != 200:
                    error_text = await response.text()
                    _logger.error(f"Failed to download page {page_id}: {response.status} - {error_text}")
                    return False

                os.makedirs(save_path_dir, exist_ok=True)
                file_path_doc = os.path.join(save_path_dir, f"{page_id}.doc")
                content = await response.read()
                async with aiofiles.open(file_path_doc, "wb") as file:
                    await file.write(content)
                return True
        except Exception as e:
            _logger.error(f"Error downloading page {page_id}: {e!s}")
            return False

    async def download_all_files_async(self, page_ids, save_path_dir, max_concurrent=1):
        connector = aiohttp.TCPConnector(limit=max_concurrent)
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = []
            for page_id in page_ids:
                task = asyncio.create_task(self.download_file_async(session, page_id, save_path_dir))
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)
            return dict(zip(page_ids, results, strict=False))

    async def download_files_async(self, page_ids, save_path_dir):
        return await self.download_all_files_async(page_ids, save_path_dir)

    def confluence_get_page_ids_by_cql(self, page_ids, last_modified_in_minutes: int | None = None) -> list[str]:
        """Return page ids that have changes in the last x minutes.

        Args:
            page_ids: List of page ids to check.
            last_modified_in_minutes: Last modified in minutes.

        Returns:
            List of page ids that have changes in the last x minutes.
            If no page ids have changes, return an empty list.

        """
        cql_query = f"id in ({','.join(map(str, page_ids))})"
        if last_modified_in_minutes and last_modified_in_minutes > 0:
            cql_query += f" and lastmodified > now('-{last_modified_in_minutes}m')"
        else:
            _logger.warning(
                "last_modified_in_minutes (%s) is invalid: %s. Ignoring...",
                last_modified_in_minutes,
                last_modified_in_minutes,
            )

        response = self.confluence.cql(cql_query)
        results = [ConfluenceCQLInstance(**item) for item in response.get("results", [])]
        return [item.id for item in results]

    def confluence_api_check_page_id_by_cql(self, page_ids, last_modified_in_minutes: int | None = None) -> list[str]:
        """Return page ids that have changes in the last x minutes.

        Args:
            page_ids: List of page ids to check.
            last_modified_in_minutes: Last modified in minutes.

        Returns:
            List of page ids that have changes in the last x minutes.
            If no page ids have changes, return an empty list.

        """
        if not page_ids:
            return []
        result_ids = []
        batch_size = 20
        for i in range(0, len(page_ids), batch_size):
            page_ids_batch = page_ids[i : i + batch_size]
            result_ids.extend(self.confluence_get_page_ids_by_cql(page_ids_batch, last_modified_in_minutes))

        return result_ids

    def get_page_by_id(self, page_id):
        url = f"{self.base_url}/rest/api/content/{page_id}"
        response = requests.get(url, headers=self.headers, auth=self.auth)

        if response.status_code == 200:
            return ConfluenceApiResponse.from_api_response(response.json())
        if response.status_code == 404:
            _logger.error(f"Page with ID {page_id} not found.")
            return None
        _logger.error(f"Failed to fetch page with ID {page_id}: {response.status_code} - {response.text}")
        raise RequestException(f"Failed to fetch page with ID {page_id}: {response.status_code} - {response.text}")

    async def get_child_pages(self, parent_id):
        """Get child pages for a parent page."""
        url = f"{self.base_url}/rest/api/content/{parent_id}/child/page"
        retry = 3
        for _ in range(retry):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=self.headers, auth=self.aio_auth) as response:
                        if response.status == 200:
                            content = await response.json()
                            child_pages = content.get("results", [])
                            return [{"id": child.get("id"), "title": child.get("title")} for child in child_pages]
                        if response.status == 429:
                            _logger.warning(
                                "Rate limited (429) for parent ID %s, retrying %s of %s...",
                                parent_id,
                                _ + 1,
                                retry,
                            )
                            await asyncio.sleep(2 ** (_ + 1))  # Exponential backoff
                            continue
                        content = await response.text()
                        _logger.warning("HTTP %s for parent ID %s: %s", response.status, parent_id, content)
                        return None
            except Exception:
                _logger.exception("Failed to fetch child pages for parent ID %s", parent_id)
                await asyncio.sleep(2)
        return None

    async def get_all_child_pages(self, page_id):
        """Get all child pages for a parent page."""
        result = []

        async def recurse(pid):
            """Recursively get all child pages for a parent page."""
            child_pages = await self.get_child_pages(parent_id=pid)
            if not child_pages:
                return
            for child in child_pages:
                result.append({"id": child["id"], "title": child["title"]})
                await recurse(child["id"])

        await recurse(page_id)
        return result

    async def add_comment(self, page_id: str, comment_body: str) -> dict | None:
        """Add a comment to a Confluence page using Atlassian SDK.

        Args:
            page_id (str): The Confluence page ID (e.g., "123456789").
            comment_body (str): The comment text to add.

        Returns:
            dict | None: JSON response from the API containing the created comment.

        """
        try:
            _logger.info(f"Adding comment to page {page_id} using Atlassian SDK")
            
            # Use the Atlassian SDK to add comment
            # The SDK handles authentication and API endpoints automatically
            # Run the synchronous SDK call in a thread pool to avoid blocking
            import asyncio
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self.confluence.add_comment, page_id, comment_body)
            
            if result:
                _logger.info(f"Comment added successfully: {result}")
                return result
            else:
                _logger.error(f"Failed to add comment to page {page_id} using SDK")
                return None
                
        except Exception as e:
            _logger.error(f"Error adding comment to page {page_id}: {e}")
            return None


# Global Confluence service instance
confluence_service = ConfluenceService()

async def add_comment_to_page(page_id: str, comment_body: str) -> dict:
    """Add a comment to a Confluence page.

    Args:
        page_id (str): The Confluence page ID (e.g., "123456789").
        comment_body (str): The comment text to add.

    Returns:
        dict: Response from the API containing the created comment or error information.

    """
    try:
        result = await confluence_service.add_comment(page_id, comment_body)
        if result:
            return {
                "success": True,
                "message": f"Comment added successfully to page {page_id}",
                "comment_id": result.get("id"),
                "created": result.get("created"),
                "author": result.get("author", {}).get("displayName", "Unknown")
            }
        else:
            return {
                "success": False,
                "message": f"Failed to add comment to page {page_id}. No response from API."
            }
    except Exception as e:
        _logger.error("Error adding comment to page '%s': %s", page_id, e)
        return {
            "success": False,
            "message": f"Error adding comment to page {page_id}: {str(e)}"
        }
