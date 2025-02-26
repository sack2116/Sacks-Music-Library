import os
import base64
import pandas as pd
import dash
from dash import html, dcc, Output, Input
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TALB, TPE1, TCON, TYER, USLT, APIC
from flask import Flask, send_file

# Load song metadata (recursively searching inside subfolders)
def load_songs(directory):
    songs = []
    for root, _, files in os.walk(directory):  # Recursively search
        for file in files:
            if file.endswith(".mp3"):
                file_path = os.path.join(root, file)
                title, album, artist, genre, year, duration = extract_metadata(file_path)
                artwork = get_artwork_thumbnail(file_path)
                lyrics = load_lyrics(file_path)
                songs.append({
                    "title": title, 
                    "album": album, 
                    "artist": artist,
                    "genre": genre,
                    "year": year,
                    "duration": duration, 
                    "artwork": artwork, 
                    "file_path": file_path, 
                    "lyrics": lyrics
                })
    
    return pd.DataFrame(songs)

# Extract metadata (title, album, artist, genre, year)
def extract_metadata(file_path):
    audio = MP3(file_path, ID3=ID3)
    
    title = audio.tags.get("TIT2", TIT2(encoding=3, text=["Unknown Title"])).text[0]
    album = audio.tags.get("TALB", TALB(encoding=3, text=["Unknown Album"])).text[0]
    artist = audio.tags.get("TPE1", TPE1(encoding=3, text=["Unknown Artist"])).text[0]
    genre = audio.tags.get("TCON", TCON(encoding=3, text=["Unknown Genre"])).text[0]
    year = audio.tags.get("TYER", TYER(encoding=3, text=["Unknown Year"])).text[0]
    
    return title, album, artist, genre, year, format_duration(file_path)

# Format duration to mm:ss
def format_duration(file_path):
    audio = MP3(file_path)
    total_seconds = int(audio.info.length)
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes}:{seconds:02d}"

# Load lyrics from a corresponding .txt file
def load_lyrics(file_path):
    lyrics_file = file_path.replace(".mp3", ".txt")  
    if os.path.exists(lyrics_file):
        with open(lyrics_file, "r", encoding="utf-8") as f:
            return f.read()
    return "No Lyrics Available"

# Get artwork thumbnail (base64 encoding for Dash)
def get_artwork_thumbnail(file_path):
    audio = MP3(file_path, ID3=ID3)
    for tag in audio.tags.values():
        if isinstance(tag, APIC):  
            return f"data:image/jpeg;base64,{base64.b64encode(tag.data).decode()}"
    return "/assets/default_artwork.jpg"  

# Load songs from directory
music_dir = r"C:\Users\hdomi\Desktop\AI Voice Clips\Mis Canciones Oficiales\Songs Database project\Music\OwnSongs"
df = load_songs(music_dir)

# Initialize Dash app
app = dash.Dash(__name__)
server = app.server  

# Custom route to serve MP3 files
@app.server.route("/music/<path:song_path>")
def serve_music(song_path):
    full_path = os.path.join(music_dir, song_path)
    if os.path.exists(full_path):
        return send_file(full_path, mimetype="audio/mpeg")
    return "File Not Found", 404

# Layout
app.layout = html.Div([
    html.H1("🎵 Music Player", style={"textAlign": "center"}),

    # Available Songs List
    html.H3("Available Songs"),
    html.Div([
        html.Button(
            f"{row['title']} - {row['album']} ({row['duration']})",
            id=f"song-btn-{i}",
            n_clicks=0,
            style={
                "display": "block", 
                "margin": "5px", 
                "cursor": "pointer", 
                "padding": "10px", 
                "borderRadius": "5px", 
                "background": "#007BFF", 
                "color": "white",
                "width": "100%",
                "textAlign": "left",
                "border": "none"
            }
        )
        for i, row in df.iterrows()
    ], id="songs-list"),

    # Now Playing Section
    html.H3("Now Playing"),
    html.Div([
        html.Img(id="now-playing-artwork", style={"width": "150px", "height": "150px", "borderRadius": "10px"}),
        html.Div([
            html.H2(id="now-playing-title"),
            html.P(id="now-playing-album"),
            html.P(id="now-playing-artist"),
            html.P(id="now-playing-genre"),
            html.P(id="now-playing-year"),
            html.P(id="now-playing-duration")
        ], style={"paddingLeft": "20px"})
    ], style={"display": "flex", "alignItems": "center"}),

    # Audio Player
    html.Div([
        html.Audio(id="audio-player", controls=True, style={"width": "100%", "marginTop": "10px"}),
    ], style={"textAlign": "center"}),

    # Lyrics Section
    html.H3("Lyrics"),
    html.Div(id="lyrics", style={"white-space": "pre-wrap", "border": "1px solid #ddd", "padding": "10px", "borderRadius": "5px"})
])

# Callback for updating Now Playing & Music Player
@app.callback(
    [Output("now-playing-title", "children"),
     Output("now-playing-album", "children"),
     Output("now-playing-artist", "children"),
     Output("now-playing-genre", "children"),
     Output("now-playing-year", "children"),
     Output("now-playing-duration", "children"),
     Output("now-playing-artwork", "src"),
     Output("audio-player", "src"),
     Output("lyrics", "children")],
    [Input(f"song-btn-{i}", "n_clicks") for i in range(len(df))]
)
def update_now_playing(*args):
    ctx = dash.callback_context
    if not ctx.triggered:
        return "Select a Song", "Album: N/A", "Artist: N/A", "Genre: N/A", "Year: N/A", "Duration: N/A", "/assets/default_artwork.jpg", "", "No Lyrics Available"

    # Get the ID of the button that was clicked
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]

    # Extract song index from button ID
    try:
        song_index = int(triggered_id.split("-")[-1])
    except ValueError:
        return "Select a Song", "Album: N/A", "Artist: N/A", "Genre: N/A", "Year: N/A", "Duration: N/A", "/assets/default_artwork.jpg", "", "No Lyrics Available"

    selected_song = df.iloc[song_index]

    # Generate correct MP3 file path for serving
    mp3_file = f"/music/{os.path.relpath(selected_song['file_path'], music_dir)}"

    return (selected_song["title"], 
            f"Album: {selected_song['album']}",
            f"Artist: {selected_song['artist']}",
            f"Genre: {selected_song['genre']}",
            f"Year: {selected_song['year']}",
            f"Duration: {selected_song['duration']}",
            selected_song["artwork"], 
            mp3_file,  
            selected_song["lyrics"])

# Run Dash app
if __name__ == '__main__':
    app.run_server(debug=True)
