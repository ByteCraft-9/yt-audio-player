import sqlite3
import os
from typing import List, Optional
from core.yt_service import TrackInfo

DB_PATH = "favorites.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id TEXT UNIQUE,
            title TEXT,
            uploader TEXT,
            webpage_url TEXT,
            duration INTEGER,
            sort_order INTEGER
        )
    """)
    conn.commit()
    conn.close()

def add_favorite(track: TrackInfo):
    if not track.video_id:
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get max sort_order
    cursor.execute("SELECT MAX(sort_order) FROM favorites")
    row = cursor.fetchone()
    next_order = (row[0] + 1) if row[0] is not None else 0

    cursor.execute("""
        INSERT OR REPLACE INTO favorites (video_id, title, uploader, webpage_url, duration, sort_order)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (track.video_id, track.title, track.uploader, track.webpage_url, track.duration, next_order))
    conn.commit()
    conn.close()

def remove_favorite(video_id: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM favorites WHERE video_id = ?", (video_id,))
    conn.commit()
    conn.close()

def is_favorite(video_id: str) -> bool:
    if not video_id:
        return False
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM favorites WHERE video_id = ?", (video_id,))
    result = cursor.fetchone() is not None
    conn.close()
    return result

def get_all_favorites() -> List[TrackInfo]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT video_id, title, uploader, webpage_url, duration FROM favorites ORDER BY sort_order ASC")
    rows = cursor.fetchall()
    conn.close()
    
    tracks = []
    for r in rows:
        tracks.append(TrackInfo(
            video_id=r[0],
            title=r[1],
            uploader=r[2],
            webpage_url=r[3],
            duration=r[4]
        ))
    return tracks

def update_order(video_ids: List[str]):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for index, vid in enumerate(video_ids):
        cursor.execute("UPDATE favorites SET sort_order = ? WHERE video_id = ?", (index, vid))
    conn.commit()
    conn.close()
