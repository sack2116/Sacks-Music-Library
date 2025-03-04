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

# Generate song list dynamically
def create_song_list(filtered_df):
    return [
        html.Div([
            html.Img(src=row['artwork'], className="song-artwork"),
            html.Button(
                f"{row['title']} - {row['album']} ({row['duration']})",
                id=f"song-btn-{i}",
                n_clicks=0,
                className="song-button"
            )
        ], className="song-item")
        for i, row in filtered_df.iterrows()
    ]

song_list = create_song_list(df)

# Layout
app.layout = html.Div([
    html.H1("Isaac's Personal Music Library and Player", style={"text-align": "center"}),

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
    }),  # ✅ Comma added here

    # Now Playing Section (Updated Styling with Video)
    html.Div([
        html.H3("Now Playing", className="section-heading now-playing-button"),

        # 🎥 Background Video
        html.Div([
            html.Video(
                id="background-video",
                src="/assets/Sacks.mp4",
                autoPlay=True,
                loop=True,
                muted=True,
                controls=False,
                style={
                    "width": "320px",
                    "height": "265px",
                    "border-radius": "0px",
                    "position": "absolute",
                    "top": "-75px",
                    "right": "20px",
                    "z-index": "5"
                }
            )
        ], style={"position": "relative", "width": "100%", "text-align": "right"}),  # ✅ Comma added here

        html.Img(id="now-playing-artwork", style={"width": "120px", "height": "120px", "border-radius": "10px"}),
        html.H2(id="now-playing-title"),
        html.P(id="now-playing-details"),

        # Audio Player
        html.Div([
            html.Audio(id="audio-player", controls=True, autoPlay=True, style={"width": "90%", "height": "80px"})
        ], style={
            "border": "2px solid #40E0D0",
            "border-radius": "5px",
            "padding": "10px",
            "width": "90%",
            "margin-top": "10px"
        }),

        # Music Controls
        html.Div([
            html.Button("⏮️ Previous", id="prev-btn", className="control-button"),
            html.Button("⏭️ Next", id="next-btn", className="control-button")
        ], style={"text-align": "center", "margin-top": "10px"})
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


# Callbacks
@app.callback(
    [Output("now-playing-title", "children"),
     Output("now-playing-artwork", "src"),
     Output("now-playing-details", "children"),
     Output("audio-player", "src"),
     Output("lyrics", "children")],  
    [Input(f"song-btn-{i}", "n_clicks") for i in range(len(df))] +
    [Input("prev-btn", "n_clicks"), Input("next-btn", "n_clicks")],
    prevent_initial_call=True
)
def update_now_playing(*clicks):
    global current_song_index
    ctx = dash.callback_context

    if not ctx.triggered:
        return "Select a Song", "/assets/default_artwork.jpg", "", "", "No Lyrics Available"

    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if "song-btn" in triggered_id:
        current_song_index = int(triggered_id.split("-")[-1])
    elif triggered_id == "prev-btn":
        current_song_index = (current_song_index - 1) % len(df)
    elif triggered_id == "next-btn":
        current_song_index = (current_song_index + 1) % len(df)

    song = df.iloc[current_song_index]
    song_url = f"/music/{song['file_path']}"
    
    return (song["title"], 
            song["artwork"], 
            f"Album: {song['album']} | Artist: {song['artist']} | Year: {song['year']} | Length: {song['duration']}",
            song_url,
            song["lyrics"])

if __name__ == '__main__':
    app.run_server(debug=True)
