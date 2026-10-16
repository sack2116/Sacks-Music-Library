"""Build the static share site (one page per song) from the MusicAlbums folder.

Each share page plays only its own song; the site has no page that lists the library. Its home page
and any unknown address send visitors back to the last song they opened (or the featured song).

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
    for sub in ("assets", "media", "art", "s"):
        os.makedirs(os.path.join(out_dir, sub))
    open(os.path.join(out_dir, BUILD_MARKER), "w").close()
    open(os.path.join(out_dir, ".nojekyll"), "w").close()  # serve files as-is on GitHub Pages


def copy_assets(out_dir):
    with open(os.path.join(ASSETS_DIR, "style.css"), encoding="utf-8") as f:
        css = f.read().replace('url("/assets/Background.png")', 'url("Background.png")')
    with open(os.path.join(out_dir, "assets", "style.css"), "w", encoding="utf-8") as f:
        f.write(css)
    shutil.copy2(os.path.join(ASSETS_DIR, "Background.png"), os.path.join(out_dir, "assets", "Background.png"))
    shutil.copy2(os.path.join(SOURCE_DIR, "static.css"), os.path.join(out_dir, "assets", "static.css"))


def copy_song_files(out_dir, album_list):
    """Copy each song's audio and artwork (album cover when the MP3 has none); return the songs."""
    songs = []
    for album in album_list:
        cover_path = album_cover_path(album)
        for song in album["songs"]:
            song = dict(song, audio=f"media/{song['id']}.mp3", art=None)
            shutil.copy2(song["file_path"], os.path.join(out_dir, song["audio"]))
            artwork = get_artwork(song["file_path"])
            if artwork:
                data, mime = artwork
                song["art"] = f"art/{song['id']}{IMAGE_EXTENSIONS.get(mime.lower(), '.jpg')}"
                with open(os.path.join(out_dir, song["art"]), "wb") as f:
                    f.write(data)
            elif cover_path:
                song["art"] = f"art/{song['id']}{os.path.splitext(cover_path)[1].lower()}"
                shutil.copy2(cover_path, os.path.join(out_dir, song["art"]))
            songs.append(song)
    return songs


def write_share_page(out_dir, site_url, song):
    """Share page for one song: plays just that song (no albums). Link previews (Facebook, WhatsApp, X...)
    read its tags."""
    with open(os.path.join(SOURCE_DIR, "song.html"), encoding="utf-8") as f:
        page = f.read()
    values = {
        "SONG_ID": song["id"],
        "PAGE_TITLE": f"{song['title']} - {song['artist']}",
        "DESCRIPTION": f"Listen to \"{song['title']}\" from the album {song['album']}",
        "SITE_TITLE": SITE_TITLE,
        "PAGE_URL": f"{site_url}/s/{quote(song['id'])}/",
        "IMAGE_URL": f"{site_url}/{song['art']}" if song["art"] else "",
        "AUDIO_URL": f"{site_url}/{song['audio']}",
        "SONG_TITLE": song["title"],
        "DETAILS": f"Album: {song['album']} | Artist: {song['artist']} | Year: {song['year']} | Length: {song['duration']}",
        "ART": f"../../{song['art']}" if song["art"] else "",
        "AUDIO": f"../../{song['audio']}",
        "LYRICS": song["lyrics"],
    }
    for key, value in values.items():
        page = page.replace("{{" + key + "}}", html.escape(value))
    song_dir = os.path.join(out_dir, "s", song["id"])
    os.makedirs(song_dir)
    with open(os.path.join(song_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)


def write_redirect(path, songs_base, featured):
    """Home page / unknown address: send the visitor back to the last song they opened from a share link
    (remembered in their browser), or to the featured song. songs_base is where the /s/ pages live."""
    fallback = html.escape(f"{songs_base}{quote(featured)}/")
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(SITE_TITLE)}</title>
<meta name="robots" content="noindex">
<script>
(function () {{
    var songsBase = {json.dumps(songs_base)};
    var song = {json.dumps(featured)};
    try {{
        var last = localStorage.getItem("sacks-last-song");
        var here = location.pathname.replace(/\\/$/, "");
        // Ignore it if this page is already that song's address (a song that was removed), to avoid a loop
        if (last && /^[a-z0-9-]+$/.test(last) && here.slice(-("/s/" + last).length) !== "/s/" + last) {{
            song = last;
        }} else if (last) {{
            localStorage.removeItem("sacks-last-song");
        }}
    }} catch (err) {{ /* storage blocked: use the featured song */ }}
    location.replace(songsBase + song + "/");
}})();
</script>
<noscript><meta http-equiv="refresh" content="0; url={fallback}"></noscript>
</head>
<body style="background:#000"></body>
</html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=os.path.join(BASE_DIR, "site"), help="output folder (default: ./site)")
    parser.add_argument("--site-url", default=os.environ.get("SITE_URL", SHARE_SITE_URL),
                        help="public address of the site, used in link previews")
    args = parser.parse_args()
    out_dir = os.path.abspath(args.out)
    site_url = args.site_url.rstrip("/")

    album_list, _ = load_library()
    prepare_output(out_dir)
    copy_assets(out_dir)
    songs = copy_song_files(out_dir, album_list)
    for song in songs:
        write_share_page(out_dir, site_url, song)
    # No library page: the home page and any unknown address open the visitor's last shared song
    # (or the featured song)
    featured = next((s["id"] for s in songs if s["featured"]), songs[0]["id"])
    write_redirect(os.path.join(out_dir, "index.html"), "s/", featured)
    write_redirect(os.path.join(out_dir, "404.html"), f"{site_url}/s/", featured)
    print(f"Built share pages for {len(songs)} songs into {out_dir}")
    print(f"Share links look like {site_url}/s/{featured}/")


if __name__ == "__main__":
    main()
