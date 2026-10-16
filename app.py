import os
import json
import html as html_lib
from urllib.parse import parse_qs, quote
import dash
from dash import html, dcc, Output, Input, State, ALL, ctx
from dash.exceptions import PreventUpdate
from flask import send_file, abort, request, Response
from werkzeug.middleware.proxy_fix import ProxyFix
from library import BASE_DIR, SITE_TITLE, SHARE_SITE_URL, load_library, get_artwork, album_cover_path
ALBUM_LIST, SONGS = load_library()
SONG_BY_ID = {s["id"]: s for s in SONGS}
ALBUM_BY_KEY = {a["key"]: a for a in ALBUM_LIST}
DEFAULT_SONG_ID = next((s["id"] for s in SONGS if s["featured"]), SONGS[0]["id"] if SONGS else None)
# Favorites setup (JSON file, stores song titles)
FAVORITES_FILE = os.path.join(BASE_DIR, "favorites.json")
def load_favorites():
    if os.path.exists(FAVORITES_FILE):
        with open(FAVORITES_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []
def save_favorites(favorites):
    with open(FAVORITES_FILE, "w") as f:
        json.dump(favorites, f)
# Initialize Dash app
app = dash.Dash(__name__,
                title=SITE_TITLE,
                external_stylesheets=[
                    'https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap'
                ],
                meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1.0"}])
server = app.server
# Render runs the app behind a proxy; this makes share links use the public https address
server.wsgi_app = ProxyFix(server.wsgi_app, x_proto=1, x_host=1)
# Serve a song's audio (supports seeking)
@server.route("/music/<song_id>")
def serve_music(song_id):
    song = SONG_BY_ID.get(song_id) or abort(404)
    return send_file(song["file_path"], mimetype="audio/mpeg", conditional=True)
# Serve an album's cover image
@server.route("/album-cover/<album_key>")
def serve_album_cover(album_key):
    album = ALBUM_BY_KEY.get(album_key) or abort(404)
    cover_path = album_cover_path(album) or abort(404)
    return send_file(cover_path, max_age=86400)
# Serve a song's artwork from its MP3 tags (falls back to the album cover)
@server.route("/artwork/<song_id>")
def serve_artwork(song_id):
    song = SONG_BY_ID.get(song_id) or abort(404)
    artwork = get_artwork(song["file_path"])
    if artwork:
        data, mime = artwork
        return Response(data, mimetype=mime, headers={"Cache-Control": "public, max-age=86400"})
    return serve_album_cover(song["album_key"])
# Share links go to the static share site when it is set up (always online, see build_static.py),
# otherwise to this app's own share page below
def share_url(song_id):
    if SHARE_SITE_URL:
        return f"{SHARE_SITE_URL.rstrip('/')}/s/{quote(song_id)}/"
    return f"/s/{quote(song_id)}"
# Share link for one song. Link previews (WhatsApp, Messages, Facebook...) read the tags on this
# page; people who open it are sent straight to the player with that song playing.
@server.route("/s/<song_id>")
def share_song(song_id):
    song = SONG_BY_ID.get(song_id) or abort(404)
    root = request.url_root
    player_url = f"{root}?song={quote(song_id)}"
    image_url = f"{root}artwork/{quote(song_id)}"
    title = html_lib.escape(f"{song['title']} - {song['artist']}")
    description = html_lib.escape(f"Listen to \"{song['title']}\" from the album {song['album']}")
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta property="og:type" content="music.song">
<meta property="og:site_name" content="{html_lib.escape(SITE_TITLE)}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:image" content="{image_url}">
<meta property="og:url" content="{root}s/{quote(song_id)}">
<meta name="twitter:card" content="summary_large_image">
<meta http-equiv="refresh" content="0; url={player_url}">
</head>
<body style="background:#000;color:#fff;font-family:Arial,sans-serif;text-align:center;padding-top:40px">
<p>Opening <a style="color:#40E0D0" href="{player_url}">{html_lib.escape(song['title'])}</a>...</p>
<script>window.location.replace({json.dumps(player_url)});</script>
</body>
</html>"""
    return Response(page, mimetype="text/html")
# One song row: play button, favorite heart and share button
def song_row(song, number, favorites, list_type):
    is_favorite = song["title"] in favorites
    if list_type == "album":
        play_id = {"type": "song-btn", "song": song["id"]}
        heart_id = {"type": "fav-btn", "song": song["id"]}
        label = [html.Span(f"{number}.", className="track-num"),
                 html.Span(song["title"], className="song-title"),
                 html.Span(song["duration"], className="song-duration")]
    else:
        play_id = {"type": "fav-song-btn", "song": song["id"]}
        heart_id = {"type": "unfav-btn", "song": song["id"]}
        label = [html.Span(song["title"], className="song-title"),
                 html.Span(song["album"], className="song-album"),
                 html.Span(song["duration"], className="song-duration")]
    return html.Div([
        html.Button(label, id=play_id, className="song-button"),
        html.Button("❤️", id=heart_id, title="Favorite",
                    className="favorite-button active" if is_favorite else "favorite-button"),
        html.Button("🔗", className="share-button", title="Share this song",
                    **{"data-share-url": share_url(song["id"]), "data-share-title": song["title"]}),
    ], className="song-item")
# Expandable album: header with cover and name, and the album's songs (hidden until opened)
def album_section(album, favorites):
    cover = html.Img(src=f"/album-cover/{album['key']}", className="album-cover") if album["cover"] else \
        html.Div("💿", className="album-cover album-cover-placeholder")
    count = len(album["songs"])
    return html.Div([
        html.Button([
            cover,
            html.Div([
                html.Div(album["name"], className="album-name"),
                html.Div(f"{count} song{'s' if count != 1 else ''}", className="album-meta"),
            ], className="album-info"),
            html.Span("▸", className="album-chevron"),
        ], id={"type": "album-toggle", "album": album["key"]}, className="album-header"),
        html.Div([song_row(song, i + 1, favorites, "album") for i, song in enumerate(album["songs"])],
                 id={"type": "album-songs", "album": album["key"]},
                 className="album-songs", style={"display": "none"}),
    ], className="album")
# The page is built per visit so it shows the current favorites
def serve_layout():
    favorites = load_favorites()
    return html.Div([
        dcc.Location(id="url", refresh=False),
        html.H1([
            html.Span("🎵", style={"color": "#ff66c4", "font-size": "36px", "margin-right": "10px"}),
            SITE_TITLE
        ], style={"text-align": "center"}),
        html.Div([
            html.Div([
                html.Div([
                    dcc.RadioItems(
                        id="view-mode",
                        options=[{"label": "💿 Albums", "value": "albums"},
                                 {"label": "❤️ Favorites", "value": "favorites"}],
                        value="albums",
                        className="view-toggle",
                        inputClassName="view-toggle-input",
                        labelClassName="view-toggle-label",
                    ),
                ], className="song-list-header"),
                html.Div([album_section(album, favorites) for album in ALBUM_LIST], id="albums-view"),
                html.Div(id="favorites-view", style={"display": "none"}),
            ], className="song-list"),
            # Lyrics Section
            html.Div([
                html.H3("Lyrics", className="section-heading"),
                html.Div(id="lyrics", className="lyrics-content")
            ], className="lyrics-container"),
        ], className="songs-lyrics-container"),
        # Now Playing Section
        html.Div([
            html.H3("Now Playing", className="section-heading now-playing-button"),
            html.Div(style={"position": "relative", "width": "100%", "text-align": "right"}, children=[
                html.Video(
                    id="background-video",
                    src="/assets/Sacks.mp4",
                    autoPlay=True,
                    loop=True,
                    muted=True,
                    controls=False,
                    style={
                        "width": "310px",
                        "height": "270px",
                        "border-radius": "10px",
                        "position": "absolute",
                        "top": "-60px",
                        "right": "20px",
                        "z-index": "5"
                    }
                )
            ]),
            html.Img(id="now-playing-artwork", src="",
                     style={"width": "120px", "height": "120px"}),
            html.H2(id="now-playing-title", children="Select a Song"),
            html.P(id="now-playing-details", children=""),
            # Shown when the browser blocks autoplay until the visitor interacts with the page
            html.Button("▶ Tap to play", id="tap-to-play", className="control-button tap-to-play"),
            html.Div([
                # player.js starts playback whenever a new song loads
                html.Audio(id="audio-player", controls=True,
                           style={"width": "100%", "height": "80px"})
            ], style={
                "border": "2px solid #40E0D0",
                "border-radius": "10px",
                "padding": "10px",
                "width": "100%",
                "margin-top": "10px"
            }),
            html.Div([
                html.Button("⏮️ Previous", id="prev-btn", className="control-button"),
                html.Button("❤️", id="fav-now-playing", title="Favorite", className="favorite-button"),
                html.Button("🔗", id="share-now-playing", className="share-button", title="Share this song"),
                html.Button("⏭️ Next", id="next-btn", className="control-button")
            ], style={"text-align": "center", "margin-top": "20px",
                      "display": "flex", "justify-content": "center", "align-items": "center"}),
            html.Div(id="toast", className="toast"),
            # Stores for state management:
            dcc.Store(id="current-song", data=None),
            dcc.Store(id="open-albums", data=[]),
            dcc.Store(id="favorites-store", data=favorites),
        ], className="music-player")
    ])
app.layout = serve_layout
# SELECT SONG: on page load (featured song, or ?song=<id> from a share link), song clicks, Previous / Next.
# Previous and Next move within the album of the song that is playing.
@app.callback(
    Output("current-song", "data"),
    [Input("url", "search"),
     Input({"type": "song-btn", "song": ALL}, "n_clicks"),
     Input({"type": "fav-song-btn", "song": ALL}, "n_clicks"),
     Input("prev-btn", "n_clicks"),
     Input("next-btn", "n_clicks")],
    State("current-song", "data")
)
def select_song(search, _song_clicks, _fav_song_clicks, _prev, _next, current_id):
    trigger = ctx.triggered_id
    # Page load (Dash may report any input as the trigger here): play the shared song or the featured one
    if current_id is None:
        requested = parse_qs((search or "").lstrip("?")).get("song", [None])[0]
        song_id = requested if requested in SONG_BY_ID else DEFAULT_SONG_ID
        if song_id is None:
            raise PreventUpdate
        return song_id
    # Buttons that were just (re)rendered also fire with no clicks; ignore those
    if trigger is None or trigger == "url" or not ctx.triggered[0]["value"]:
        raise PreventUpdate
    if isinstance(trigger, dict):
        return trigger["song"]
    if current_id not in SONG_BY_ID:
        raise PreventUpdate
    album_songs = ALBUM_BY_KEY[SONG_BY_ID[current_id]["album_key"]]["songs"]
    position = next(i for i, s in enumerate(album_songs) if s["id"] == current_id)
    step = -1 if trigger == "prev-btn" else 1
    return album_songs[(position + step) % len(album_songs)]["id"]
# Update Now-Playing display for the selected song
@app.callback(
    [Output("now-playing-title", "children"),
     Output("now-playing-artwork", "src"),
     Output("now-playing-details", "children"),
     Output("audio-player", "src"),
     Output("lyrics", "children"),
     Output("share-now-playing", "data-share-url"),
     Output("share-now-playing", "data-share-title")],
    Input("current-song", "data")
)
def update_now_playing_display(song_id):
    song = SONG_BY_ID.get(song_id)
    if song is None:
        raise PreventUpdate
    return (song["title"],
            f"/artwork/{song['id']}",
            f"Album: {song['album']} | Artist: {song['artist']} | Year: {song['year']} | Length: {song['duration']}",
            f"/music/{song['id']}",
            song["lyrics"],
            share_url(song["id"]),
            song["title"])
# Highlight the playing song in the album lists
@app.callback(
    Output({"type": "song-btn", "song": ALL}, "className"),
    Input("current-song", "data")
)
def highlight_playing_song(song_id):
    return ["song-button playing" if o["id"]["song"] == song_id else "song-button"
            for o in ctx.outputs_list]
# Open / close albums. The album of the playing song is opened automatically.
@app.callback(
    Output("open-albums", "data"),
    [Input({"type": "album-toggle", "album": ALL}, "n_clicks"),
     Input("current-song", "data")],
    State("open-albums", "data")
)
def update_open_albums(_toggle_clicks, song_id, open_albums):
    open_albums = list(open_albums or [])
    trigger = ctx.triggered_id
    # On page load Dash may report an album header as the trigger with no clicks; treat that like a song change
    if isinstance(trigger, dict) and ctx.triggered[0]["value"]:
        album_key = trigger["album"]
        if album_key in open_albums:
            open_albums.remove(album_key)
        else:
            open_albums.append(album_key)
        return open_albums
    song = SONG_BY_ID.get(song_id)
    if song is None or song["album_key"] in open_albums:
        raise PreventUpdate
    return open_albums + [song["album_key"]]
@app.callback(
    [Output({"type": "album-songs", "album": ALL}, "style"),
     Output({"type": "album-toggle", "album": ALL}, "className")],
    Input("open-albums", "data")
)
def show_open_albums(open_albums):
    keys = [o["id"]["album"] for o in ctx.outputs_list[0]]
    styles = [{"display": "block" if key in open_albums else "none"} for key in keys]
    classes = ["album-header open" if key in open_albums else "album-header" for key in keys]
    return styles, classes
# Switch between the Albums and Favorites views
@app.callback(
    [Output("albums-view", "style"),
     Output("favorites-view", "style")],
    Input("view-mode", "value")
)
def switch_view(view_mode):
    show, hide = {"display": "block"}, {"display": "none"}
    return (hide, show) if view_mode == "favorites" else (show, hide)
# List of favorite songs
@app.callback(
    Output("favorites-view", "children"),
    Input("favorites-store", "data")
)
def show_favorites(favorites):
    favorite_songs = [s for s in SONGS if s["title"] in favorites]
    if not favorite_songs:
        return html.P("No favorites yet. Tap ❤️ on a song to add it here.", className="empty-message")
    return [song_row(song, i + 1, favorites, "favorites") for i, song in enumerate(favorite_songs)]
# Update the favorites store when a heart is clicked (album lists, favorites list or now-playing)
@app.callback(
    Output("favorites-store", "data"),
    [Input({"type": "fav-btn", "song": ALL}, "n_clicks"),
     Input({"type": "unfav-btn", "song": ALL}, "n_clicks"),
     Input("fav-now-playing", "n_clicks")],
    [State("favorites-store", "data"),
     State("current-song", "data")],
    prevent_initial_call=True
)
def update_favorites_store(_fav_clicks, _unfav_clicks, _now_playing_clicks, favorites, current_id):
    trigger = ctx.triggered_id
    if trigger is None or not ctx.triggered[0]["value"]:
        raise PreventUpdate
    song_id = trigger["song"] if isinstance(trigger, dict) else current_id
    song = SONG_BY_ID.get(song_id)
    if song is None:
        raise PreventUpdate
    new_favorites = list(favorites)
    if song["title"] in new_favorites:
        new_favorites.remove(song["title"])
    else:
        new_favorites.append(song["title"])
    save_favorites(new_favorites)
    return new_favorites
# Update heart buttons from the favorites store
@app.callback(
    Output({"type": "fav-btn", "song": ALL}, "className"),
    Input("favorites-store", "data")
)
def update_album_hearts(favorites):
    return ["favorite-button active" if SONG_BY_ID[o["id"]["song"]]["title"] in favorites else "favorite-button"
            for o in ctx.outputs_list]
@app.callback(
    Output("fav-now-playing", "className"),
    [Input("favorites-store", "data"),
     Input("current-song", "data")]
)
def update_now_playing_favorite_status(favorites, song_id):
    song = SONG_BY_ID.get(song_id)
    return "favorite-button active" if song and song["title"] in favorites else "favorite-button"
if __name__ == '__main__':
    app.run_server(debug=True)
