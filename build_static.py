"""Build the static share site (player + one share page per song) from the MusicAlbums folder.

The output folder can be hosted on any static host (GitHub Pages, Cloudflare Pages, Netlify), which
stays online all the time, so share links and social media previews load instantly.

    python build_static.py                  # builds into ./site
    python -m http.server -d site 8000      # preview at http://localhost:8000
"""
import os
import json
import shutil
import argparse
import html
from urllib.parse import quote
from library import BASE_DIR, SITE_TITLE, SHARE_SITE_URL, load_library, get_artwork, album_cover_path

SOURCE_DIR = os.path.join(BASE_DIR, "static_site")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
BUILD_MARKER = ".static-build"
IMAGE_EXTENSIONS = {"image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


def prepare_output(out_dir):
    # Only ever delete a folder this script created
    if os.path.exists(out_dir):
        if not os.path.exists(os.path.join(out_dir, BUILD_MARKER)):
            raise SystemExit(f"{out_dir} exists and was not made by build_static.py; choose another --out folder")
        shutil.rmtree(out_dir)
    for sub in ("assets", "media", "art", "covers", "s"):
        os.makedirs(os.path.join(out_dir, sub))
    open(os.path.join(out_dir, BUILD_MARKER), "w").close()
    open(os.path.join(out_dir, ".nojekyll"), "w").close()  # serve files as-is on GitHub Pages


def copy_assets(out_dir):
    with open(os.path.join(ASSETS_DIR, "style.css"), encoding="utf-8") as f:
        css = f.read().replace('url("/assets/Background.png")', 'url("Background.png")')
    with open(os.path.join(out_dir, "assets", "style.css"), "w", encoding="utf-8") as f:
        f.write(css)
    for name in ("Background.png", "Sacks.mp4"):
        shutil.copy2(os.path.join(ASSETS_DIR, name), os.path.join(out_dir, "assets", name))
    shutil.copy2(os.path.join(SOURCE_DIR, "static.css"), os.path.join(out_dir, "assets", "static.css"))
    shutil.copy2(os.path.join(SOURCE_DIR, "player.js"), os.path.join(out_dir, "assets", "player.js"))


def build_library(out_dir, album_list):
    """Copy songs, artwork and covers; return the song data the player and share pages use."""
    albums = []
    for album in album_list:
        cover = None
        cover_path = album_cover_path(album)
        if cover_path:
            cover = f"covers/{album['key']}{os.path.splitext(cover_path)[1].lower()}"
            shutil.copy2(cover_path, os.path.join(out_dir, cover))
        songs = []
        for song in album["songs"]:
            audio = f"media/{song['id']}.mp3"
            shutil.copy2(song["file_path"], os.path.join(out_dir, audio))
            art = cover
            artwork = get_artwork(song["file_path"])
            if artwork:
                data, mime = artwork
                art = f"art/{song['id']}{IMAGE_EXTENSIONS.get(mime.lower(), '.jpg')}"
                with open(os.path.join(out_dir, art), "wb") as f:
                    f.write(data)
            songs.append({key: song[key] for key in ("id", "title", "album", "album_key", "artist", "year",
                                                      "duration", "lyrics")} | {"audio": audio, "art": art})
        albums.append({"key": album["key"], "name": album["name"], "cover": cover, "songs": songs})
    return albums


def write_index(out_dir, site_url, library_data, og_image):
    with open(os.path.join(SOURCE_DIR, "index.html"), encoding="utf-8") as f:
        page = f.read()
    # Keep "</script>" inside lyrics from ending the data block
    library_json = json.dumps(library_data, ensure_ascii=False).replace("</", "<\\/")
    page = (page.replace("{{SITE_TITLE}}", html.escape(SITE_TITLE))
                .replace("{{SITE_URL}}", html.escape(site_url))
                .replace("{{OG_IMAGE}}", html.escape(og_image))
                .replace("{{LIBRARY_JSON}}", library_json))
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)


def write_share_page(out_dir, site_url, song):
    """Small page per song: link previews (Facebook, WhatsApp, X...) read its tags, visitors go to the player."""
    player_url = f"../../?song={quote(song['id'])}"
    title = html.escape(f"{song['title']} - {song['artist']}")
    description = html.escape(f"Listen to \"{song['title']}\" from the album {song['album']}")
    image = html.escape(f"{site_url}/{song['art']}") if song["art"] else ""
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{description}">
<meta property="og:type" content="music.song">
<meta property="og:site_name" content="{html.escape(SITE_TITLE)}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{html.escape(site_url)}/s/{quote(song['id'])}/">
<meta property="og:image" content="{image}">
<meta property="og:image:alt" content="{html.escape(song['title'])} cover art">
<meta property="og:audio" content="{html.escape(site_url)}/{song['audio']}">
<meta property="og:audio:type" content="audio/mpeg">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{description}">
<meta name="twitter:image" content="{image}">
<meta http-equiv="refresh" content="0; url={player_url}">
</head>
<body style="background:#000;color:#fff;font-family:Arial,sans-serif;text-align:center;padding-top:40px">
<p>Opening <a style="color:#40E0D0" href="{player_url}">{html.escape(song['title'])}</a>...</p>
<script>window.location.replace({json.dumps(player_url)});</script>
</body>
</html>"""
    song_dir = os.path.join(out_dir, "s", song["id"])
    os.makedirs(song_dir)
    with open(os.path.join(song_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=os.path.join(BASE_DIR, "site"), help="output folder (default: ./site)")
    parser.add_argument("--site-url", default=os.environ.get("SITE_URL", SHARE_SITE_URL),
                        help="public address of the site, used in link previews")
    args = parser.parse_args()
    out_dir = os.path.abspath(args.out)
    site_url = args.site_url.rstrip("/")

    album_list, songs = load_library()
    prepare_output(out_dir)
    copy_assets(out_dir)
    albums = build_library(out_dir, album_list)
    featured = next((s["id"] for s in songs if s["featured"]), songs[0]["id"])
    library_data = {"siteTitle": SITE_TITLE, "featured": featured, "albums": albums}
    featured_album = next(a for a in albums if any(s["id"] == featured for s in a["songs"]))
    og_image = f"{site_url}/{featured_album['cover']}" if featured_album["cover"] else ""
    write_index(out_dir, site_url, library_data, og_image)
    for album in albums:
        for song in album["songs"]:
            write_share_page(out_dir, site_url, song)
    print(f"Built {len(songs)} songs in {len(albums)} albums into {out_dir}")
    print(f"Share links look like {site_url}/s/{featured}/")


if __name__ == "__main__":
    main()
