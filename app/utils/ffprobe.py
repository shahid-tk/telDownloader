import asyncio
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


async def extract_metadata(file_path: str) -> Optional[Dict[str, Any]]:
    """
    Extracts metadata from a video file using ffprobe.
    """
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        file_path,
    ]

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            logger.error(f"ffprobe error on {file_path}: {stderr.decode()}")
            return None

        data = json.loads(stdout.decode())
        format_info = data.get("format", {})
        format_tags = format_info.get("tags", {})

        # ffprobe tags can be lowercase or uppercase depending on container format (e.g. MKV vs MP4)
        metadata = {k.lower(): v for k, v in format_tags.items()}
        metadata["__format_name__"] = format_info.get("format_name", "")
        return metadata

    except Exception as e:
        logger.exception(f"Failed to extract metadata using ffprobe for {file_path}: {e}")
        return None


def get_format_name(metadata: Optional[Dict[str, Any]]) -> Optional[str]:
    if not metadata:
        return None
    return metadata.get("__format_name__")


def get_movie_title(metadata: Dict[str, Any]) -> Optional[str]:
    return metadata.get("title")


def get_show_details(metadata: Dict[str, Any]) -> tuple[Optional[str], Optional[int], Optional[int]]:
    series_name = metadata.get("show") or metadata.get("series")

    season_num = None
    try:
        if "season_number" in metadata:
            season_num = int(metadata["season_number"])
    except ValueError:
        pass

    episode_num = None
    try:
        if "episode_sort" in metadata:
            episode_num = int(metadata["episode_sort"])
    except ValueError:
        pass

    return series_name, season_num, episode_num
