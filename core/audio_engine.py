"""
audio_engine.py
Audio-only playback engine built on libVLC (via python-vlc).

Why VLC instead of QtMultimedia/DirectShow:
YouTube's audio stream URLs only respond correctly when the request
carries the same User-Agent (and referrer) yt-dlp used to obtain them.
QtMultimedia's Windows backend (DirectShow) offers no way to attach custom
HTTP headers, so it gets rejected by YouTube's servers (surfaces as
DirectShowPlayerService::doRender error 0x80040218). libVLC's network
stack accepts per-media HTTP options, so it plays these streams reliably
on every platform. It also never touches a video output -- audio only.

Requires the separate VLC application to be installed (any 64-bit build
matching your Python's bitness): https://www.videolan.org/vlc/
"""

from __future__ import annotations

from typing import List, Optional

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from core.yt_service import TrackInfo

SKIP_MS = 3_000  # forward/backward skip amount
POLL_INTERVAL_MS = 300
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

try:
    import vlc  # type: ignore
    VLC_IMPORT_ERROR: Optional[str] = None
except Exception as exc:  # noqa: BLE001 - libvlc missing/not found
    vlc = None  # type: ignore
    VLC_IMPORT_ERROR = str(exc)


class AudioEngine(QObject):
    """Owns the libVLC player instance and the current playlist/queue."""

    track_changed = pyqtSignal(object)             # TrackInfo
    position_changed = pyqtSignal(int)              # ms
    duration_changed = pyqtSignal(int)              # ms
    playing_state_changed = pyqtSignal(bool)        # True = playing
    error_occurred = pyqtSignal(str)
    playlist_index_changed = pyqtSignal(int, int)   # current, total
    track_needs_resolution = pyqtSignal(object)     # TrackInfo awaiting stream_url

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        if vlc is None:
            raise RuntimeError(
                "Could not load libVLC. Install the VLC application "
                "(64-bit build matching your Python) from "
                f"https://www.videolan.org/vlc/ and restart.\n\nDetails: {VLC_IMPORT_ERROR}"
            )

        # --no-video: belt-and-braces, we never feed it video anyway.
        self._instance = vlc.Instance("--no-video", "--quiet")
        self.player = self._instance.media_player_new() # type: ignore

        self.queue: List[TrackInfo] = []
        self.current_index: int = -1
        self._playback_rate: float = 1.0
        self._advancing_from_end: bool = False

        self._last_duration_ms: int = -1
        self._last_is_playing: Optional[bool] = None
        self._reported_ended: bool = False

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll)
        self._poll_timer.start()

    # ---------- loading ----------

    def load_single(self, track: TrackInfo) -> None:
        self.queue = [track]
        self.current_index = 0
        self._play_current()

    def load_queue(self, tracks: List[TrackInfo], start_index: int = 0) -> None:
        self.queue = tracks
        self.current_index = start_index
        self._play_current()

    def _play_current(self) -> None:
        if not (0 <= self.current_index < len(self.queue)):
            return
        track = self.queue[self.current_index]
        if track.is_resolved:
            self._set_media(track)
        # If unresolved, the caller (UI) resolves it and calls
        # update_resolved_track() -- see main_window._resolve_and_play().

    def update_resolved_track(self, track: TrackInfo) -> None:
        """Called once a queued (unresolved) TrackInfo has been resolved
        with an actual stream_url -- swaps it into the queue and plays it."""
        if 0 <= self.current_index < len(self.queue):
            self.queue[self.current_index] = track
        self._set_media(track)

    def _set_media(self, track: TrackInfo) -> None:
        media = self._instance.media_new(track.stream_url) # type: ignore

        user_agent = DEFAULT_USER_AGENT
        referrer = "https://www.youtube.com/"
        if track.http_headers:
            user_agent = track.http_headers.get("User-Agent", user_agent)
            referrer = track.http_headers.get("Referer", referrer)
        media.add_option(f":http-user-agent={user_agent}")
        media.add_option(f":http-referrer={referrer}")

        self.player.set_media(media)
        self.player.play()
        self.player.set_rate(self._playback_rate)

        self._last_duration_ms = -1
        self._reported_ended = False

        self.track_changed.emit(track)
        self.playlist_index_changed.emit(self.current_index, len(self.queue))

    # ---------- transport controls ----------

    def toggle_play_pause(self) -> None:
        if self.player.is_playing():
            self.player.pause()
        else:
            self.player.play()

    def play(self) -> None:
        self.player.play()

    def pause(self) -> None:
        self.player.pause()

    def stop(self) -> None:
        self.player.stop()

    def seek_forward(self, ms: int = SKIP_MS) -> None:
        duration = self.player.get_length()
        new_pos = self.player.get_time() + ms
        if duration > 0:
            new_pos = min(new_pos, duration)
        self.set_position(max(new_pos, 0))

    def seek_backward(self, ms: int = SKIP_MS) -> None:
        self.set_position(max(self.player.get_time() - ms, 0))

    def set_position(self, ms: int) -> None:
        self.player.set_time(int(ms))

    def set_volume(self, volume_0_100: int) -> None:
        self.player.audio_set_volume(int(volume_0_100))

    def set_playback_rate(self, rate: float) -> None:
        self._playback_rate = rate
        self.player.set_rate(rate)

    # ---------- queue navigation ----------

    @property
    def has_next(self) -> bool:
        return self.current_index + 1 < len(self.queue)

    @property
    def has_previous(self) -> bool:
        return self.current_index > 0

    def current_track(self) -> Optional[TrackInfo]:
        if 0 <= self.current_index < len(self.queue):
            return self.queue[self.current_index]
        return None

    def next_track_needs_resolution(self) -> Optional[TrackInfo]:
        """Advances the index and returns the (possibly unresolved) next
        track, or None if at the end of the queue."""
        if not self.has_next:
            return None
        self.current_index += 1
        track = self.queue[self.current_index]
        if track.is_resolved:
            self._set_media(track)
            return None
        return track

    def previous_track_needs_resolution(self) -> Optional[TrackInfo]:
        if not self.has_previous:
            return None
        self.current_index -= 1
        track = self.queue[self.current_index]
        if track.is_resolved:
            self._set_media(track)
            return None
        return track

    # ---------- polling (libVLC has no reliable cross-platform Qt signals) --

    def _poll(self) -> None:
        if self.player is None or self.player.get_media() is None:
            return

        duration = self.player.get_length()
        if duration > 0 and duration != self._last_duration_ms:
            self._last_duration_ms = duration
            self.duration_changed.emit(duration)

        position = self.player.get_time()
        if position >= 0:
            self.position_changed.emit(position)

        is_playing = bool(self.player.is_playing())
        if is_playing != self._last_is_playing:
            self._last_is_playing = is_playing
            self.playing_state_changed.emit(is_playing)

        state = self.player.get_state()

        if state == vlc.State.Error: # type: ignore
            self.error_occurred.emit(
                "VLC could not play this stream (it may be region-locked, "
                "age-restricted, or the link expired)."
            )
            return

        if state == vlc.State.Ended and not self._reported_ended: # type: ignore
            self._reported_ended = True
            unresolved = self.next_track_needs_resolution()
            if unresolved is not None:
                self.track_needs_resolution.emit(unresolved)
