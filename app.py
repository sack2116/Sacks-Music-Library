import os
import base64
import json  # Used to store favorite songs
import pandas as pd
import dash
from dash import html, dcc, Output, Input, State
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TALB, TPE1, TCON, TYER, USLT, APIC
from flask import Flask, send_file
import glob

# Define the root music directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MUSIC_DIR = os.path.join(BASE_DIR, "MusicAlbums")
FAVORITES_FILE = os.path.join(BASE_DIR, "favorites.json")  # Store favorite songs

# Load favorite songs from JSON file
def load_favorites():
    if os.path.exists(FAVORITES_FILE):
        with open(FAVORITES_FILE, "r") as f:
            return set(json.load(f))  # Store as a set for quick lookup
    return set()

# Save favorite songs to JSON file
def save_favorites(favorites):
    with open(FAVORITES_FILE, "w") as f:
        json.dump(list(favorites), f)

# Load song metadata
def load_songs(directory):
    songs = []
    favorites = load_favorites()  # Load favorite state
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
                    "is_favorite": file_path in favorites  # Check if song is favorited
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
            ),
            html.Button(
                "❤️" if row["is_favorite"] else "♡",
                id=f"fav-btn-{i}",
                n_clicks=0,
                className="favorite-button"
            )
        ], className="song-item")
        for i, row in filtered_df.iterrows()
    ]

# Ensure song_list is initialized before being used
song_list = create_song_list(df)

app.layout = html.Div([
    html.H1([
        html.Span("🎵", style={"color": "#ff66c4", "font-size": "36px", "margin-right": "10px"}),
        "Isaac's Personal Music Library and Player"
    ], style={"text-align": "center"}),


    # Songs Section
    html.Div([
        html.H3("Available Songs"),
        html.Div(song_list, id="songs-list")
    ]),

    # Now Playing Section (Restored Version + Favorite Button)
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
        html.Img(id="now-playing-artwork", style={"width": "120px", "height": "120px", "margin-top": "20px"}),
        html.H2(id="now-playing-title"),
        html.P(id="now-playing-details"),
        html.Audio(id="audio-player", controls=True, autoPlay=True),
        html.Button("❤️", id="fav-now-btn", n_clicks=0),
        html.Button("⏮️ Previous", id="prev-btn"),
        html.Button("⏭️ Next", id="next-btn"),
    ]),

    # Favorites Section
    html.Div([
        html.H3("❤️ Favorite Songs"),
        html.Ul(id="favorites-list")
    ])
])

# Callbacks
@app.callback(
    [Output("now-playing-title", "children"),
     Output("now-playing-artwork", "src"),
     Output("now-playing-details", "children"),
     Output("audio-player", "src")],
    [Input(f"song-btn-{i}", "n_clicks") for i in range(len(df))] +
    [Input("prev-btn", "n_clicks"), Input("next-btn", "n_clicks")],
    prevent_initial_call=True
)
def update_now_playing(*clicks):
    global current_song_index
    ctx = dash.callback_context

    if not ctx.triggered:
        return "Select a Song", "", "", ""

    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if "song-btn" in triggered_id:
        current_song_index = int(triggered_id.split("-")[-1])
    elif triggered_id == "prev-btn":
        current_song_index = (current_song_index - 1) % len(df)
    elif triggered_id == "next-btn":
        current_song_index = (current_song_index + 1) % len(df)

    song = df.iloc[current_song_index]
    return song["title"], song["artwork"], f"{song['artist']} - {song['album']}", f"/music/{song['file_path']}"

@app.callback(
    Output("favorites-list", "children"),
    Input("fav-now-btn", "n_clicks"),
    prevent_initial_call=True
)
def add_to_favorites(n_clicks):
    song_title = df.iloc[current_song_index]["title"]
    favorites = load_favorites()
    favorites.add(song_title)
    save_favorites(favorites)
    return [html.Li(song) for song in favorites]

if __name__ == '__main__':
    app.run_server(debug=True)
