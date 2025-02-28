
import os
import base64
import pandas as pd
import dash
from dash import html, dcc, Output, Input
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TALB, TPE1, TCON, TYER, USLT, APIC
from flask import Flask, send_file
import glob

# Get the base directory where the script is located (inside the GitHub repo)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Define the music directory relative to the repo
MUSIC_DIR = os.path.join(BASE_DIR, "Music", "OwnSongs", "Sacks-Music-Library")
LYRICS_DIR = os.path.join(BASE_DIR, "Lyrics")

# Load song metadata (recursively searching inside subfolders)
def load_songs(directory):
    songs = []
    for root, _, files in os.walk(directory):  
        for file in files:
            if file.endswith(".mp3"):
                file_path = os.path.join(root, file)
                title, album, artist, genre, year, lyrics = extract_metadata(file_path)
                duration = format_duration(file_path)
                artwork = get_artwork_thumbnail(file_path)
                songs.append({
                    "title": title, 
                    "album": album, 
                    "artist": artist,
                    "genre": genre,
                    "year": year,
                    "duration": duration, 
                    "artwork": artwork, 
                    "file_path": file_path.replace(BASE_DIR, ""),  # Store relative path
                    "lyrics": lyrics
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
    song_name = os.path.splitext(os.path.basename(file_path))[0]
    lyrics_file = os.path.join(LYRICS_DIR, f"{song_name}.txt")
    if os.path.exists(lyrics_file):
        with open(lyrics_file, "r", encoding="utf-8") as f:
            return f.read()
    return "No Lyrics Available"

# Format duration
def format_duration(file_path):
    audio = MP3(file_path)
    total_seconds = int(audio.info.length)
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes}:{seconds:02d}"

# Get artwork thumbnail
def get_artwork_thumbnail(file_path):
    audio = MP3(file_path, ID3=ID3)
    for tag in audio.tags.values():
        if isinstance(tag, APIC):  
            return f"data:image/jpeg;base64,{base64.b64encode(tag.data).decode()}"
    return os.path.join("assets", "default_artwork.jpg")

# Load songs
df = load_songs(MUSIC_DIR)

# Initialize Dash app
app = dash.Dash(__name__)
server = app.server  

@app.server.route("/music/<path:song_path>")
def serve_music(song_path):
    full_path = os.path.abspath(os.path.join(BASE_DIR, song_path))  # Resolve path dynamically
    if os.path.exists(full_path):
        return send_file(full_path, mimetype="audio/mpeg")
    return "File Not Found", 404

# App layout
app.layout = html.Div([
    html.H1("Isaac's Personal Music Library and Player", style={"text-align": "center"}),

    html.Div([
        html.Div([
            html.H3("Available Songs"),
            html.Div([
                html.Button(f"{row['title']} - {row['album']} ({row['duration']})", id=f"song-btn-{i}", n_clicks=0)
                for i, row in df.iterrows()
            ], id="songs-list")
        ], style={"width": "48%"}),

        html.Div([html.H3("Lyrics"), html.Div(id="lyrics")], style={"width": "48%"})
    ], style={"display": "flex", "justify-content": "space-between"}),

    html.Div([
        html.H3("Now Playing"),
        html.Img(id="now-playing-artwork", style={"width": "120px", "height": "120px"}),
        html.H2(id="now-playing-title"),
        html.P(id="now-playing-details"),
        html.Audio(id="audio-player", controls=True, autoPlay=True)
    ], className="music-player")
])

if __name__ == "__main__":
    app.run_server(debug=True)
