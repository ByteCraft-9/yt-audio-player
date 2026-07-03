"""
yt_service.py
Thin wrapper around yt-dlp for:
  - extracting a direct, playable audio stream URL for a single video
  - flat-listing entries of a playlist (fast, no per-video resolution)
  - searching YouTube (title + channel only)

All network / extraction calls in this module are BLOCKING and should be
run off the Qt main thread (see core/workers.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import yt_dlp


# Prefer a pre-muxed, widely-decodable audio-only format (m4a/aac).
# Falls back to the best available audio stream if m4a isn't offered.
AUDIO_FORMAT = "bestaudio[ext=m4a]/bestaudio/best"


@dataclass
class TrackInfo:
    """A single track, either fully resolved (has stream_url) or a
    lightweight reference (needs resolve_stream() before it can be played)."""
    video_id: str
    title: str
    uploader: str
    webpage_url: str
    duration: Optional[int] = None
    stream_url: Optional[str] = None
    http_headers: Optional[dict] = None

    @property
    def is_resolved(self) -> bool:
        return self.stream_url is not None


def _base_opts() -> dict:
    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": False,
        "skip_download": True,
        "extract_flat": False,
    }


def resolve_stream(url_or_id: str) -> TrackInfo:
    """Resolve a single video (by URL or ID) into a playable TrackInfo
    with a direct audio stream URL."""
    opts = _base_opts()
    opts["format"] = AUDIO_FORMAT
    opts["noplaylist"] = True

    with yt_dlp.YoutubeDL(opts) as ydl: # type: ignore
        info = ydl.extract_info(url_or_id, download=False)

    return TrackInfo(
        video_id=info.get("id", ""),
        title=info.get("title", "Unknown title"), # type: ignore
        uploader=info.get("uploader") or info.get("channel") or "Unknown channel",
        webpage_url=info.get("webpage_url", url_or_id),
        duration=info.get("duration"),
        stream_url=info.get("url"),
        http_headers=info.get("http_headers") or {},
    )


def extract_playlist(url: str) -> List[TrackInfo]:
    """Fast, flat listing of a playlist's entries (titles/ids only,
    no stream URLs yet -- resolve each on demand when it's about to play)."""
    opts = _base_opts()
    opts["extract_flat"] = "in_playlist"

    with yt_dlp.YoutubeDL(opts) as ydl: # type: ignore
        info = ydl.extract_info(url, download=False)

    entries = info.get("entries") if isinstance(info, dict) else None
    if not entries:
        # Not actually a playlist -- treat as a single video reference.
        return [
            TrackInfo(
                video_id=info.get("id", ""),
                title=info.get("title", "Unknown title"), # type: ignore
                uploader=info.get("uploader") or info.get("channel") or "Unknown channel",
                webpage_url=info.get("webpage_url", url),
                duration=info.get("duration"),
            )
        ]

    tracks: List[TrackInfo] = []
    for e in entries:
        if not e:
            continue
        vid = e.get("id", "")
        tracks.append(
            TrackInfo(
                video_id=vid,
                title=e.get("title", "Unknown title"),
                uploader=e.get("uploader") or e.get("channel") or "Unknown channel",
                webpage_url=e.get("url") or f"https://www.youtube.com/watch?v={vid}",
                duration=e.get("duration"),
            )
        )
    return tracks


def search(query: str, limit: int = 15) -> List[TrackInfo]:
    """Search YouTube, returning lightweight results (title + channel only)."""
    opts = _base_opts()
    opts["extract_flat"] = "in_playlist"

    search_key = f"ytsearch{limit}:{query}"
    with yt_dlp.YoutubeDL(opts) as ydl: # type: ignore
        info = ydl.extract_info(search_key, download=False)

    entries = info.get("entries", []) if isinstance(info, dict) else []
    results: List[TrackInfo] = []
    for e in entries:
        if not e:
            continue
        vid = e.get("id", "")
        results.append(
            TrackInfo(
                video_id=vid,
                title=e.get("title", "Unknown title"),
                uploader=e.get("uploader") or e.get("channel") or "Unknown channel",
                webpage_url=f"https://www.youtube.com/watch?v={vid}",
                duration=e.get("duration"),
            )
        )
    return results


def looks_like_url(text: str) -> bool:
    text = text.strip().lower()
    return text.startswith("http://") or text.startswith("https://")
