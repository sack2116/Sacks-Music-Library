"""Song library shared by the Dash player (app.py) and the static share site (build_static.py)."""
import os
import glob
import unicodedata
import re
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC
# Define directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MUSIC_DIR = os.path.join(BASE_DIR, "MusicAlbums")
# Album display settings. Keys are folder names inside MusicAlbums; albums are listed in this order
# (folders not listed here are added after these, using the folder name).
ALBUMS = [
    {"folder": "Exhaltado Dios", "name": "Exhaltado es Dios", "cover": "Exhaltado.png"},
    {"folder": "LoveFamily", "name": "Love Family", "cover": "LoveFamily.jpg"},
    {"folder": "Principios", "name": "Principios", "cover": "Principios.png"},
]
# Song that plays when the player opens (path relative to MusicAlbums). It is listed first in its album.
FEATURED_SONG = "Exhaltado Dios/Exhaltado Dios/Exaltado Es Dios.mp3"
# Titles to show instead of the MP3's title tag (path relative to MusicAlbums)
TITLE_OVERRIDES = {
    FEATURED_SONG: "Exaltado es Dios",  # the file's tag still says "Exaltado es el Rey"
}
SITE_TITLE = "Isaac's Personal Music Library and Player"
# Public address of the static share site (GitHub Pages). Share buttons link to <SHARE_SITE_URL>/s/<song>/
SHARE_SITE_URL = "https://sack2116.github.io/Sacks-Music-Library"
# Turn a name into a URL-friendly id, e.g. "Santo Santo Santo!" -> "santo-santo-santo"
def slugify(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "song"
# Read a text tag from an MP3, falling back to a default
def get_tag(tags, key, default):
    if tags is not None and key in tags and tags[key].text:
        return str(tags[key].text[0])
    return default
# Load lyrics from a .txt file if available
def load_lyrics(file_path):
    lyrics_file = os.path.splitext(file_path)[0] + ".txt"
    if os.path.exists(lyrics_file):
        with open(lyrics_file, "r", encoding="utf-8") as f:
            return f.read()
    lyrics_dir = os.path.dirname(file_path)
    txt_files = glob.glob(os.path.join(lyrics_dir, "*.txt"))
    if txt_files:
        with open(txt_files[0], "r", encoding="utf-8") as f:
            return f.read()
    return "No Lyrics Available"
# Format duration as minutes:seconds
def format_duration(length):
    minutes = int(length // 60)
    seconds = int(length % 60)
    return f"{minutes}:{seconds:02}"
# Track number tag ("3" or "3/10") as an int for sorting
def track_number(tags):
    match = re.match(r"\d+", get_tag(tags, "TRCK", ""))
    return int(match.group()) if match else 9999
# Artwork embedded in an MP3's tags as (image bytes, mime type), or None
def get_artwork(file_path):
    tags = MP3(file_path, ID3=ID3).tags
    for tag in (tags.values() if tags else []):
        if isinstance(tag, APIC):
            return tag.data, tag.mime or "image/jpeg"
    return None
# Path of an album's cover image, or None
def album_cover_path(album):
    if not album["cover"]:
        return None
    cover_path = os.path.join(MUSIC_DIR, album["folder"], album["cover"])
    return cover_path if os.path.exists(cover_path) else None
# Scan MusicAlbums: every top-level folder is an album, every MP3 inside it (at any depth) is a song
def load_library(directory=MUSIC_DIR):
    print(f"Scanning directory: {directory}")
    album_settings = {a["folder"]: a for a in ALBUMS}
    albums = {}
    for root, _, files in os.walk(directory):
        for file in sorted(files):
            if not file.lower().endswith(".mp3"):
                continue
            file_path = os.path.join(root, file)
            music_path = os.path.relpath(file_path, directory).replace(os.sep, "/")
            if "/" not in music_path:
                continue  # MP3s must be inside an album folder
            folder = music_path.split("/")[0]
            audio = MP3(file_path, ID3=ID3)
            tags = audio.tags
            settings = album_settings.get(folder, {})
            album = albums.setdefault(folder, {
                "key": slugify(folder),
                "folder": folder,
                "name": settings.get("name", folder),
                "cover": settings.get("cover"),
                "songs": [],
            })
            album["songs"].append({
                "title": TITLE_OVERRIDES.get(music_path, get_tag(tags, "TIT2", os.path.splitext(file)[0])),
                "album": album["name"],
                "album_key": album["key"],
                "artist": get_tag(tags, "TPE1", "Unknown Artist"),
                "year": get_tag(tags, "TYER", get_tag(tags, "TDRC", "Unknown Year")),
                "duration": format_duration(audio.info.length),
                "featured": music_path == FEATURED_SONG,
                "track": track_number(tags),
                "file_path": file_path,
                "lyrics": load_lyrics(file_path),
            })
    # Album order: as listed in ALBUMS, then any other folders alphabetically
    order = [a["folder"] for a in ALBUMS]
    album_list = sorted(albums.values(),
                        key=lambda a: (order.index(a["folder"]) if a["folder"] in order else len(order), a["folder"].lower()))
    songs = []
    used_ids = set()
    for album in album_list:
        album["songs"].sort(key=lambda s: (not s["featured"], s["track"], s["title"].lower()))
        for song in album["songs"]:
            # Song ids are used in share links (/s/<id>), so keep them short and readable
            song_id = slugify(song["title"])
            if song_id in used_ids:
                song_id = f"{album['key']}-{song_id}"
            used_ids.add(song_id)
            song["id"] = song_id
            songs.append(song)
    print(f"Total songs loaded: {len(songs)} in {len(album_list)} albums")
    return album_list, songs
