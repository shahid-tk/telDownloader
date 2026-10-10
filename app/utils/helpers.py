import os
import re
from pathlib import Path


INVALID_FS_CHARS = r'<>:"/\|?*'
VALID_VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".m4v", ".webm", ".ts"}


def ensure_dir(path: str) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def remove_empty_dirs(path: str) -> None:
    """Recursively removes empty directories starting from the given path up to its parents."""
    p = Path(path)
    while p.exists() and p.is_dir():
        try:
            p.rmdir()
            p = p.parent
        except OSError:
            break


def parse_show_info(filename: str) -> dict | None:
    """
    Parses show title, season, and episodes directly from release filenames.
    Examples:
      - House.of.the.Dragon.S02E02.[@Series_World_TM].10 -> Show: House of the Dragon, Season: 2, Episodes: [2]
      - Friends.S10E17.E18.[@Series_World_TM].720p.x265. -> Show: Friends, Season: 10, Episodes: [17, 18]
      - Teach.You.a.Lesson.2026.S01E07... -> Show: Teach You a Lesson (2026), Season: 1, Episodes: [7]
      - Breaking.Bad.1x05.720p.mkv -> Show: Breaking Bad, Season: 1, Episodes: [5]
    """
    if not filename:
        return None

    # 1. Standard SxxExx with optional multi-episode (.Eyy, -Eyy, -yy)
    m = re.search(r"^(.*?)[._ -]+[sS](\d+)[eE](\d+)(?:[._ -]*(?:[eE]|(?<=[eE]\d{2})-)(\d+))?", filename)
    if m:
        raw_title = m.group(1)
        season = int(m.group(2))
        episodes = [int(m.group(3))]
        if m.group(4):
            episodes.append(int(m.group(4)))
    else:
        # 2. 1x05 format
        m = re.search(r"^(.*?)[._ -]+(\d+)x(\d+)", filename)
        if m:
            raw_title = m.group(1)
            season = int(m.group(2))
            episodes = [int(m.group(3))]
        else:
            return None

    # Clean up show title
    title = re.sub(r"[._]+", " ", raw_title).strip()
    # Format (Year) if ends with 4 digits e.g. 19xx or 20xx
    m_year = re.search(r"^(.*?)\s+(19\d\d|20\d\d)$", title)
    if m_year:
        title = f"{m_year.group(1)} ({m_year.group(2)})"

    return {
        "title": title,
        "season": season,
        "episodes": episodes,
    }


def extract_season_episodes(filename: str) -> tuple[int | None, list[int]]:
    """
    Extracts season number and a list of episode numbers (supporting multi-episodes).
    """
    if not filename:
        return None, []

    # Match S01E20 with optional second episode
    m1 = re.search(r"[sS](\d+)[eE](\d+)(?:[._ -]*(?:[eE]|(?<=[eE]\d{2})-)(\d+))?", filename)
    if m1:
        season = int(m1.group(1))
        episodes = [int(m1.group(2))]
        if m1.group(3):
            episodes.append(int(m1.group(3)))
        return season, episodes

    # Match 1x20
    m2 = re.search(r"(?<!\d)(\d+)x(\d+)(?!\d)", filename)
    if m2:
        return int(m2.group(1)), [int(m2.group(2))]

    return None, []


def extract_season_episode(filename: str) -> tuple[int | None, int | None]:
    """Backward compatible extraction of single season and first episode."""
    season, episodes = extract_season_episodes(filename)
    return season, (episodes[0] if episodes else None)


def sanitize_name(name: str) -> str:
    name = re.sub(r"\s+", " ", name.strip())
    return "".join("_" if c in INVALID_FS_CHARS else c for c in name)


def get_video_extension(filename: str | None, detected_fmt: str | None = None) -> str:
    """
    Validates the extension against known video formats.
    If the filename ends in a truncated extension (like .10, .HEV, .H, .WEB-, etc.),
    falls back to the container format probed from ffprobe or .mkv.
    """
    if filename:
        _, ext = os.path.splitext(filename)
        ext = ext.lower().strip()
        if ext in VALID_VIDEO_EXTENSIONS:
            return ext

    if detected_fmt:
        df = detected_fmt.lower()
        if "matroska" in df:
            return ".mkv"
        if "mp4" in df or "mov" in df:
            return ".mp4"
        if "webm" in df:
            return ".webm"
        if "avi" in df:
            return ".avi"

    return ".mkv"


def get_extension(filename: str | None) -> str:
    return get_video_extension(filename)


def format_season_episode(season: int, episodes: list[int] | int, ext: str) -> str:
    """
    Formats episode string according to Plex/Jellyfin standards.
    Single episode: s02e02.mkv
    Multi-episode:  s10e17-e18.mkv
    """
    if not ext.startswith("."):
        ext = f".{ext}"

    if isinstance(episodes, int):
        return f"s{season:02d}e{episodes:02d}{ext}"
    if not episodes:
        return f"s{season:02d}{ext}"
    if len(episodes) == 1:
        return f"s{season:02d}e{episodes[0]:02d}{ext}"

    ep_str = "-".join(f"e{ep:02d}" for ep in episodes)
    return f"s{season:02d}{ep_str}{ext}"


async def get_all_available_shows(uploads_repo, shows_dir: str) -> list[str]:
    """
    Returns a sorted list of unique show names found in MongoDB uploads_repo
    and on disk in shows_dir.
    """
    shows_set = set()

    # From MongoDB
    try:
        db_shows = await uploads_repo.get_shows()
        if db_shows:
            shows_set.update(db_shows)
    except Exception:
        pass

    # From disk
    try:
        p = Path(shows_dir)
        if p.exists() and p.is_dir():
            for item in p.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    shows_set.add(item.name)
    except Exception:
        pass

    return sorted(list(shows_set), key=lambda s: s.lower())


async def get_available_seasons(uploads_repo, shows_dir: str, show_name: str) -> list[int]:
    """
    Returns a sorted list of unique seasons for a given show from MongoDB and disk.
    """
    seasons_set = set()

    # From MongoDB
    try:
        db_seasons = await uploads_repo.get_show_seasons(show_name)
        if db_seasons:
            seasons_set.update(db_seasons)
    except Exception:
        pass

    # From disk
    try:
        show_path = Path(shows_dir) / show_name
        if show_path.exists() and show_path.is_dir():
            for item in show_path.iterdir():
                if item.is_dir():
                    m = re.search(r"Season\s*0*(\d+)", item.name, re.IGNORECASE)
                    if m:
                        seasons_set.add(int(m.group(1)))
    except Exception:
        pass

    return sorted(list(seasons_set))


async def get_next_expected_episode(uploads_repo, shows_dir: str, show_name: str, season: int) -> int:
    """
    Calculates the next expected episode number (max found + 1) for a show's season.
    Defaults to 1 if no episodes are found.
    """
    episodes_set = set()

    # From MongoDB
    try:
        db_eps = await uploads_repo.get_show_episodes(show_name, season)
        if db_eps:
            episodes_set.update(db_eps)
    except Exception:
        pass

    # From disk
    try:
        season_dir = Path(shows_dir) / show_name / f"Season {season:02d}"
        if season_dir.exists() and season_dir.is_dir():
            for file in season_dir.iterdir():
                if file.is_file():
                    _, eps = extract_season_episodes(file.name)
                    if eps:
                        episodes_set.update(eps)
    except Exception:
        pass

    return max(episodes_set) + 1 if episodes_set else 1
