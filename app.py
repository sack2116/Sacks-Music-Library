import os
import base64
import pandas as pd
import dash
from dash import html, dcc, Output, Input
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TALB, TPE1, TCON, TYER, USLT, APIC
from flask import Flask, send_file

# Define the root music directory based on the repo structure
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MUSIC_DIR = os.path.join(BASE_DIR, "MusicAlbums")

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
                relative_path = os.path.relpath(file_path, BASE_DIR)  # Use relative path for serving
                songs.append({
                    "title": title, 
                    "album": album, 
                    "artist": artist,
                    "genre": genre,
                    "year": year,
                    "duration": duration, 
                    "artwork": artwork, 
                    "file_path": relative_path,  # Updated for relative paths
                    "lyrics": lyrics
                })
    return pd.DataFrame(songs)

# Extract metadata (title, album, artist, genre, year, lyrics)
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

# Load lyrics from a .txt file with the same name as the MP3
import glob

def load_lyrics(file_path):
    lyrics_file = os.path.splitext(file_path)[0] + ".txt"

    if os.path.exists(lyrics_file):  
        with open(lyrics_file, "r", encoding="utf-8") as f:  
            return f.read()
    return "No Lyrics Available"

# Format duration to mm:ss
def format_duration(file_path):
    audio = MP3(file_path)
    total_seconds = int(audio.info.length)
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes}:{seconds:02d}"

# Get artwork thumbnail (base64 encoding for Dash)
def get_artwork_thumbnail(file_path):
    audio = MP3(file_path, ID3=ID3)
    for tag in audio.tags.values():
        if isinstance(tag, APIC):  
            return f"data:image/jpeg;base64,{base64.b64encode(tag.data).decode()}"
    return os.path.join("assets", "default_artwork.jpg")  # Use repo structure

# Load songs from the MusicAlbums directory
df = load_songs(MUSIC_DIR)

# Initialize Dash app
app = dash.Dash(__name__)
server = app.server  

@app.server.route("/music/<path:song_path>")
def serve_music(song_path):
    full_path = os.path.abspath(os.path.join(BASE_DIR, song_path))

    if os.path.exists(full_path):
        return send_file(full_path, mimetype="audio/mpeg")
    return "File Not Found", 404

# App Layout
app.layout = html.Div([
    html.H1([
        html.Span("🎵", style={"color": "#ff66c4", "font-size": "36px", "margin-right": "10px"}),
        "Isaac's Personal Music Library and Player"
    ], style={"text-align": "center"}),

    # Unified Container for Available Songs & Lyrics
    html.Div([
        html.Div([
            html.H3("Available Songs", style={"text-align": "center", "color": "#ff66c4"}),
            html.Div([
                html.Div([
                    html.Img(src=row['artwork'], style={"width": "40px", "height": "40px", "margin-right": "10px", "border-radius": "5px"}),
                    html.Button(
                        f"{row['title']} - {row['album']} ({row['duration']})",
                        id=f"song-btn-{i}",
                        n_clicks=0,
                        className="song-button"
                    )
                ], style={"display": "flex", "align-items": "center", "border-bottom": "1px solid gray", "padding": "5px"})
                for i, row in df.iterrows()
            ], id="songs-list", style={"overflow-y": "auto", "max-height": "400px", "padding": "10px"})
        ], style={"width": "48%"}),  

        html.Div([
            html.H3("Lyrics", style={"text-align": "center", "color": "#ff66c4"}),
            html.Div(id="lyrics", className="lyrics-container", style={
                "white-space": "pre-wrap",
                "overflow-y": "auto",
                "max-height": "400px",
                "padding": "10px",
                "text-align": "center",
                "height": "400px"
            })
        ], style={"width": "48%"})
    ], style={"display": "flex", "justify-content": "space-between", "gap": "4%", "padding": "15px"}),

    # Now Playing Section
    html.Div([
        html.H3("Now Playing", style={"color": "white"}),
        html.Img(id="now-playing-artwork", style={"width": "120px", "height": "120px", "margin-bottom": "10px", "border-radius": "10px"}),
        html.H2(id="now-playing-title", style={"font-size": "20px", "color": "white"}),
        html.P(id="now-playing-details", style={"color": "white"}),

        html.Div([
            html.Audio(id="audio-player", controls=True, autoPlay=True, style={"width": "100%"})
        ], style={"border": "2px solid #40E0D0", "border-radius": "5px", "padding": "10px"}),

        html.Div([
            html.Button("⏮️ Previous", id="prev-btn", className="control-button"),
            html.Button("⏭️ Next", id="next-btn", className="control-button"),
        ], style={"text-align": "center", "margin-top": "10px"})
    ], className="music-player", style={"background": "black", "border": "2px solid white", "border-radius": "10px", "padding": "20px"})
], style={"padding": "20px", "height": "100vh", "overflow-y": "scroll"})

# Store the current song index
current_song_index = 0  

@app.callback(
    [Output("now-playing-title", "children"),
     Output("now-playing-artwork", "src"),
     Output("now-playing-details", "children"),
     Output("audio-player", "src"),
     Output("lyrics", "children")],
    [Input("prev-btn", "n_clicks"),
     Input("next-btn", "n_clicks")] + [Input(f"song-btn-{i}", "n_clicks") for i in range(len(df))],
    prevent_initial_call=True
)
def update_now_playing(prev_clicks, next_clicks, *song_clicks):
    global current_song_index
    ctx = dash.callback_context

    if not ctx.triggered:
        return "Select a Song", "/assets/default_artwork.jpg", "", "", "No Lyrics Available"

    # Identify which button was clicked
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if "song-btn" in triggered_id:
        song_index = int(triggered_id.split("-")[-1])
        current_song_index = song_index
    elif triggered_id == "prev-btn":
        current_song_index = (current_song_index - 1) % len(df)
    elif triggered_id == "next-btn":
        current_song_index = (current_song_index + 1) % len(df)

    # Ensure valid song selection
    if current_song_index < 0 or current_song_index >= len(df):
        return "Select a Song", "/assets/default_artwork.jpg", "", "", "No Lyrics Available"

    selected_song = df.iloc[current_song_index]

    # Construct file paths
    mp3_file = f"/MusicAlbums/{os.path.relpath(selected_song['file_path'], music_dir)}"
    artwork = f"/assets/{selected_song['artwork']}" if selected_song["artwork"] else "/assets/default_artwork.jpg"
    lyrics = selected_song["lyrics"] if selected_song["lyrics"] else "Lyrics not available"

    return (selected_song["title"], 
            artwork, 
            f"Album: {selected_song['album']} | Artist: {selected_song['artist']} | Genre: {selected_song['genre']} | Year: {selected_song['year']}",
            mp3_file, 
            lyrics)

if __name__ == '__main__':
    app.run_server(debug=True)
