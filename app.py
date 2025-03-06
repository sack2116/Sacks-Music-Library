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
    return "No lyrics available."

# Format duration (minutes:seconds)
def format_duration(file_path):
    audio = MP3(file_path)
    length = audio.info.length
    minutes = int(length // 60)
    seconds = int(length % 60)
    return f"{minutes}:{seconds:02}"

# Create a thumbnail for artwork
def get_artwork_thumbnail(file_path):
    artwork_file = os.path.splitext(file_path)[0] + ".jpg"
    if os.path.exists(artwork_file):
        with open(artwork_file, "rb") as img:
            return "data:image/jpeg;base64," + base64.b64encode(img.read()).decode('utf-8')
    return "/assets/default_artwork.jpg"  # Default artwork

# Create DataFrame for songs
df = load_songs(MUSIC_DIR)

# Initialize Dash app
app = dash.Dash(__name__, external_stylesheets=["/assets/style.css"])
server = app.server

# Layout
app.layout = html.Div([
    html.H1("Isaac's Personal Music Library", style={"text-align": "center"}),
    
    # Filter Dropdown + Songs List Section
    html.Div([
        html.Div([
            html.Button("Available Songs", className="dropdown-label-button"),
            dcc.Dropdown(
                id="filter-dropdown",
                options=[ 
                    {"label": "All Songs", "value": "all"},
                    {"label": "Favorites", "value": "favorites"},
                    {"label": "By Album", "value": "by_album"}
                ],
                value="all",
                clearable=False,
                style={ "width": "150px", "margin-left": "10px" }
            )
        ], style={"display": "flex", "align-items": "center", "margin-bottom": "10px"}),

        html.Div(id="songs-list", className="songs-list-container")
    ]),
    
    # Now Playing Section
    html.Div([
        html.H3("Now Playing", className="section-heading"),
        html.Img(id="now-playing-artwork", style={"width": "120px", "height": "120px"}),
        html.H2(id="now-playing-title"),
        html.P(id="now-playing-details"),
        html.Audio(id="audio-player", controls=True, autoPlay=True, style={"width": "90%"}),
        html.Div([
            html.Button("⏮️", id="prev-btn"),
            html.Button("▶️", id="play-btn"),
            html.Button("⏭️", id="next-btn")
        ], style={"text-align": "center", "margin-top": "10px"}),
        html.Button("❤️", id="fav-now-playing", className="favorite-button")
    ], className="music-player")
])

# Update song list
@app.callback(
    Output("songs-list", "children"),
    [Input("filter-dropdown", "value")]
)
def filter_songs(filter_value):
    filtered_songs = df if filter_value == "all" else df[df["title"].isin(favorite_songs)]
    return [
        html.Div([
            html.Button([
                html.Img(src=song["artwork"], style={"width": "50px", "height": "50px"}),
                html.Div([
                    html.P(f"{song['title']} - {song['album']} ({song['duration']})")
                ], style={"margin-left": "10px"})
            ], id=f"song-btn-{i}", className="song-button"),
            html.Button("❤️", id=f"fav-btn-{i}", className="favorite-button", style={"color": "blue"})
        ], className="song-item") for i, song in filtered_songs.iterrows()
    ]

if __name__ == '__main__':
    app.run_server(debug=True)
