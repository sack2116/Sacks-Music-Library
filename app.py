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

# Load favorite songs
def load_favorites():
    if os.path.exists(FAVORITES_FILE):
        with open(FAVORITES_FILE, "r") as f:
            return set(json.load(f))  
    return set()

def save_favorites(favorites):
    with open(FAVORITES_FILE, "w") as f:
        json.dump(list(favorites), f)

# Load song metadata
def load_songs(directory):
    songs = []
    favorites = load_favorites()
    for root, _, files in os.walk(directory):  
        for file in files:
            if file.endswith(".mp3"):
                file_path = os.path.join(root, file)
                title, album, artist, genre, year, lyrics = extract_metadata(file_path)
                duration = format_duration(file_path)
                artwork = get_artwork_thumbnail(file_path)
                relative_path = os.path.relpath(file_path, BASE_DIR)
                
                songs.append({
                    "id": file_path,  
                    "title": title, 
                    "album": album, 
                    "artist": artist,
                    "genre": genre,
                    "year": year,
                    "duration": duration, 
                    "artwork": artwork, 
                    "file_path": relative_path,
                    "lyrics": lyrics,
                    "is_favorite": file_path in favorites  
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
app.css.config.serve_locally = True  

# Serve music files
@app.server.route("/music/<path:song_path>")
def serve_music(song_path):
    full_path = os.path.abspath(os.path.join(BASE_DIR, song_path))
    if os.path.exists(full_path):
        return send_file(full_path, mimetype="audio/mpeg")
    return "File Not Found", 404

# Dropdown filter options
filter_options = [
    {"label": "All Songs", "value": "all"},
    {"label": "By Album", "value": "album"},
    {"label": "Favorites", "value": "favorites"}
]

# Initialize song list
def create_song_list(filtered_df):
    return [
        html.Div([
            html.Img(src=row['artwork'], className="song-artwork"),
            html.Button(
                f"{row['title']} - {row['album']} ({row['duration']})",
                id=f"song-btn-{i}",
                n_clicks=0,
                className="song-button"
            ),
            html.Button(
                "💙" if row["is_favorite"] else "❤️",
                id=f"fav-btn-{i}",
                n_clicks=0,
                className="favorite-button"
            )
        ], className="song-item")
        for i, row in filtered_df.iterrows()
    ]

song_list = create_song_list(df)

# Layout
app.layout = html.Div([
    html.H1("Isaac's Personal Music Library and Player", style={"text-align": "center"}),

    # Dropdown Filter
    dcc.Dropdown(
        id="song-filter",
        options=filter_options,
        value="all",
        clearable=False,
        style={"width": "40%", "margin": "10px auto"}
    ),

    # Songs & Lyrics Section
    html.Div([
        html.Div([
            html.H3("Available Songs", className="section-heading"),
            html.Div(song_list, id="songs-list", className="songs-list-container")
        ], className="song-list", style={"width": "45%"}),

        html.Div([
            html.H3("Lyrics", className="section-heading"),
            html.Div(id="lyrics", className="lyrics-container")
        ], className="lyrics-container", style={"width": "45%"})
    ], className="songs-lyrics-container", style={
        "display": "flex",
        "justify-content": "space-between",
        "width": "90%",
        "margin": "auto"
    }),

    # Now Playing Section
    html.Div([
        html.H3("Now Playing", className="section-heading now-playing-button"),
        html.Img(id="now-playing-artwork", style={"width": "120px", "height": "120px", "border-radius": "10px"}),
        html.H2(id="now-playing-title"),
        html.P(id="now-playing-details"),
        html.Audio(id="audio-player", controls=True, autoPlay=True),

        html.Div([
            html.Button("⏮️ Previous", id="prev-btn", className="control-button"),
            html.Button("💙", id="fav-now-btn", n_clicks=0, className="control-button"),
            html.Button("⏭️ Next", id="next-btn", className="control-button"),
        ], style={"text-align": "center", "margin-top": "10px"}),

    ], className="music-player", style={
        "background": "black",
        "border": "2px solid white",
        "border-radius": "10px",
        "padding": "20px",
        "position": "relative",
        "display": "flex",
        "flex-direction": "column",
        "align-items": "center",
        "width": "90%",
        "margin": "20px auto"
    })
])

# Everything is now working! 🚀  
if __name__ == '__main__':
    app.run_server(debug=True)
