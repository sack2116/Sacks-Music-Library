import os
import base64
import json
import pandas as pd
import dash
from dash import html, dcc, Output, Input, State
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TALB, TPE1, TCON, TYER, APIC
from flask import Flask, send_file
import glob

# Define directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MUSIC_DIR = os.path.join(BASE_DIR, "MusicAlbums")
FAVORITES_FILE = os.path.join(BASE_DIR, "favorites.json")

# Load or initialize favorite songs list
def load_favorites():
    if os.path.exists(FAVORITES_FILE):
        with open(FAVORITES_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_favorites():
    with open(FAVORITES_FILE, "w") as f:
        json.dump(list(favorite_songs), f)

favorite_songs = load_favorites()

# Load song metadata
def load_songs(directory):
    songs = []
    print(f"Scanning directory: {directory}")

    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".mp3"):
                file_path = os.path.join(root, file)
                print(f"Found MP3: {file_path}")

                title, album, artist, genre, year, lyrics = extract_metadata(file_path)
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
                    "lyrics": lyrics
                })
    
    df = pd.DataFrame(songs)
    print(f"Total songs loaded: {len(df)}")
    return df

# Extract metadata
def extract_metadata(file_path):
    audio = MP3(file_path, ID3=ID3)
    title = audio.tags.get("TIT2", TIT2(encoding=3, text=["Unknown Title"])).text[0]
    album = audio.tags.get("TALB", TALB(encoding=3, text=["Unknown Album"])).text[0]
    artist = audio.tags.get("TPE1", TPE1(encoding=3, text=["Unknown Artist"])).text[0]
    genre = audio.tags.get("TCON", TCON(encoding=3, text=["Unknown Genre"])).text[0]

    year_tag = audio.tags.get("TYER") or audio.tags.get("TDRC")
    year = year_tag.text[0] if year_tag else "Unknown Year"
    lyrics = load_lyrics(file_path)

    return title, album, artist, genre, year, lyrics

# Load lyrics
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
# Layout
app.layout = html.Div([
    html.H1("Isaac's Personal Music Library and Player", style={"text-align": "center"}),

    # Filter Dropdown + Songs List Section
    html.Div([
        html.Div([
            html.Button("Available Songs", className="dropdown-label-button"),
            dcc.Dropdown(
                id="filter-dropdown",
                options=[
                    {"label": "All Songs", "value": "all"},
                    {"label": "Favorites", "value": "favorites"}
                ],
                value="all",
                clearable=False,
                style={
                    "width": "20%",
                    "display": "inline-block",
                    "background-color": "rgba(173, 216, 230, 0.8)",
                    "color": "black",
                    "border": "1px solid black",
                    "margin-left": "10px"
                }
            )
        ], style={"text-align": "right", "margin-bottom": "10px"}),

        html.Div(id="songs-list")
    ]),

    # Now Playing Section
    html.Div([
        html.H3("Now Playing", className="section-heading"),
        html.Img(id="now-playing-artwork"),
        html.H2(id="now-playing-title"),
        html.P(id="now-playing-details"),
        html.Audio(id="audio-player", controls=True, autoPlay=False),

        html.Button("❤️", id="fav-now-playing", n_clicks=0, className="favorite-button")
    ])
])

# Callbacks
@app.callback(
    Output("fav-now-playing", "style"),
    [Input("now-playing-title", "children"),
     Input("fav-now-playing", "n_clicks")],
    prevent_initial_call=True
)
def update_fav_button(song_title, n_clicks):
    global favorite_songs

    if not song_title or song_title == "Select a Song":
        return {"font-size": "24px", "color": "lightblue"}

    if song_title in favorite_songs:
        return {"font-size": "24px", "color": "red"}
    else:
        return {"font-size": "24px", "color": "lightblue"}

@app.callback(
    Output("songs-list", "children"),
    [Input("filter-dropdown", "value")]
)
def filter_songs(filter_value):
    filtered_songs = df[df["title"].isin(favorite_songs)] if filter_value == "favorites" else df

    return [
        html.Div([
            html.Button(song["title"], id=f"song-btn-{i}", className="song-button"),
            html.Button("❤️", id=f"fav-btn-{i}", n_clicks=0, className="favorite-button",
                        style={"color": "red" if song["title"] in favorite_songs else "lightblue"})
        ]) for i, song in filtered_songs.iterrows()
    ]

# Save favorites on exit
import atexit
atexit.register(save_favorites)

if __name__ == '__main__':
    app.run_server(debug=True)
