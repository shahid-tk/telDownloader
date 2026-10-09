import asyncio
import logging
from typing import Optional
import httpx

logger = logging.getLogger(__name__)


class MediaServerService:
    def __init__(
        self,
        jellyfin_url: Optional[str] = None,
        jellyfin_api_key: Optional[str] = None,
        plex_url: Optional[str] = None,
        plex_token: Optional[str] = None,
    ):
        self.jellyfin_url = jellyfin_url.rstrip("/") if jellyfin_url else None
        self.jellyfin_api_key = jellyfin_api_key.strip() if jellyfin_api_key else None
        self.plex_url = plex_url.rstrip("/") if plex_url else None
        self.plex_token = plex_token.strip() if plex_token else None

    async def scan_jellyfin(self) -> None:
        if not self.jellyfin_url or not self.jellyfin_api_key:
            return

        url = f"{self.jellyfin_url}/Library/Refresh"
        headers = {
            "X-Emby-Token": self.jellyfin_api_key,
            "Authorization": f'MediaBrowser Token="{self.jellyfin_api_key}"',
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, headers=headers)
                if res.status_code in (200, 204):
                    logger.info("Jellyfin library scan triggered successfully.")
                else:
                    logger.warning("Jellyfin scan returned HTTP %s: %s", res.status_code, res.text)
        except Exception as e:
            logger.warning("Failed to trigger Jellyfin library scan: %s", e)

    async def scan_plex(self) -> None:
        if not self.plex_url or not self.plex_token:
            return

        url = f"{self.plex_url}/library/sections/all/refresh"
        headers = {
            "X-Plex-Token": self.plex_token,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url, headers=headers)
                if res.status_code in (200, 204):
                    logger.info("Plex library scan triggered successfully.")
                else:
                    logger.warning("Plex scan returned HTTP %s: %s", res.status_code, res.text)
        except Exception as e:
            logger.warning("Failed to trigger Plex library scan: %s", e)

    async def trigger_scan(self) -> None:
        """
        Triggers library refresh on all configured media servers in the background.
        Never raises exceptions and silently skips unconfigured servers.
        """
        tasks = []
        if self.jellyfin_url and self.jellyfin_api_key:
            tasks.append(self.scan_jellyfin())
        if self.plex_url and self.plex_token:
            tasks.append(self.scan_plex())

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
