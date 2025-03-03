import os
import base64
import pandas as pd
import dash
from dash import html, dcc, Output, Input
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TALB, TPE1, TCON, TYER, APIC
from flask import Flask, send_file
import glob

# Define the root music directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MUSIC_DIR = os.path.join(BASE_DIR, "MusicAlbums")

# Load song metadata
def load_songs(directory):
    songs = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".mp3"):
                file_path = os.path.join(root, file)
                title, album, artist, genre, year = extract_metadata(file_path)
                duration = format_duration(file_path)
                artwork = get_artwork_thumbnail(file_path)
                relative_path = os.path.relpath(file_path, BASE_DIR)
                songs.append({
                    "title": title, 
                    "album": album, 
                    "artist": artist,
                    "genre": genre,
                    "year": year,
                    "duration": duration, 
                    "artwork": artwork, 
                    "file_path": relative_path,
                    "favorite": False  # Added favorite flag
                })
    return pd.DataFrame(songs)

# Extract metadata
def extract_metadata(file_path):
    audio = MP3(file_path, ID3=ID3)
    title = audio.tags.get("TIT2", TIT2(encoding=3, text=["Unknown Title"])).text[0]
    album = audio.tags.get("TALB", TALB(encoding=3, text=["Unknown Album"])).text[0]
    artist = audio.tags.get("TPE1", TPE1(encoding=3, text=["Unknown Artist"])).text[0]
    genre = audio.tags.get("TCON", TCON(encoding=3, text=["Unknown Genre"])).text[0]
    
    year_tag = audio.tags.get("TYER") or audio.tags.get("TDRC")
    year = year_tag.text[0] if year_tag else "Unknown Year"

    return title, album, artist, genre, year

# Format duration
def format_duration(file_path):
    audio = MP3(file_path)
    total_seconds = int(audio.info.length)
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes}:{seconds:02d}"

# Get artwork
def get_artwork_thumbnail(file_path):
    audio = MP3(file_path, ID3=ID3)
    for tag in audio.tags.values():
        if isinstance(tag, APIC):
            return f"data:image/jpeg;base64,{base64.b64encode(tag.data).decode()}"
    return os.path.join("assets", "default_artwork.jpg")

# Load songs
df = load_songs(MUSIC_DIR)

# Initialize Dash app
app = dash.Dash(__name__, external_stylesheets=["/assets/style.css"])
server = app.server

# Serve music files
@app.server.route("/music/<path:song_path>")
def serve_music(song_path):
    full_path = os.path.abspath(os.path.join(BASE_DIR, song_path))
    if os.path.exists(full_path):
        return send_file(full_path, mimetype="audio/mpeg")
    return "File Not Found", 404

# App Layout
app.layout = html.Div([
    html.H1("Isaac's Personal Music Library and Player", style={"text-align": "center"}),

    # Dropdown Filter
    html.Label("Filter Songs:"),
    dcc.Dropdown(
        id="filter-dropdown",
        options=[
            {"label": "All Songs", "value": "all"},
            {"label": "By Album", "value": "album"},
            {"label": "Favorites", "value": "favorites"}
        ],
        value="all",  # Default to "All Songs"
        clearable=False
    ),

    html.Div(id="songs-list", className="songs-list-container"),

    # Now Playing Section
    html.Div([
        html.H3("Now Playing", className="section-heading"),
        
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

        html.Img(id="now-playing-artwork", style={
            "width": "120px", "height": "120px", "margin-top": "20px", "border-radius": "10px", "display": "block"
        }),

        html.H2(id="now-playing-title", style={"font-size": "20px", "color": "white", "text-align": "center"}),
        html.P(id="now-playing-details", style={"color": "white", "text-align": "center"}),

        html.Audio(id="audio-player", controls=True, autoPlay=True, style={"width": "100%", "height": "80px"}),

        html.Button("❤️", id="favorite-btn", className="control-button", n_clicks=0)
    ], className="music-player")
])

# Callbacks
@app.callback(
    Output("songs-list", "children"),
    [Input("filter-dropdown", "value")]
)
def update_song_list(filter_option):
    filtered_df = df
    if filter_option == "favorites":
        filtered_df = df[df["favorite"]]
    elif filter_option == "album":
        filtered_df = df.sort_values("album")

    song_items = [
        html.Div([
            html.Img(src=row['artwork'], className="song-artwork"),
            html.Button(
                f"{row['title']} - {row['album']} ({row['duration']})",
                id=f"song-btn-{i}",
                n_clicks=0,
                className="song-button"
            ),
            html.Button(
                "❤️" if row["favorite"] else "🤍",
                id=f"fav-btn-{i}",
                n_clicks=0,
                className="favorite-button"
            )
        ], className="song-item")
        for i, row in filtered_df.iterrows()
    ]

    return song_items

# Update Now Playing
@app.callback(
    [Output("now-playing-title", "children"),
     Output("now-playing-artwork", "src"),
     Output("now-playing-details", "children"),
     Output("audio-player", "src")],
    [Input(f"song-btn-{i}", "n_clicks") for i in range(len(df))],
    prevent_initial_call=True
)
def update_now_playing(*clicks):
    ctx = dash.callback_context
    if not ctx.triggered:
        return "Select a Song", "/assets/default_artwork.jpg", "", ""

    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
    index = int(triggered_id.split("-")[-1])

    song = df.iloc[index]
    song_url = f"/music/{song['file_path']}"

    return song["title"], song["artwork"], f"Album: {song['album']} | Artist: {song['artist']} | Genre: {song['genre']} | Year: {song['year']}", song_url

# Update Favorite Status
@app.callback(
    Output("songs-list", "children"),
    [Input(f"fav-btn-{i}", "n_clicks") for i in range(len(df))]
)
def toggle_favorite(*clicks):
    ctx = dash.callback_context
    if not ctx.triggered:
        return update_song_list("all")

    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
    index = int(triggered_id.split("-")[-1])

    df.at[index, "favorite"] = not df.at[index, "favorite"]
    return update_song_list("all")

if __name__ == '__main__':
    app.run_server(debug=True)
