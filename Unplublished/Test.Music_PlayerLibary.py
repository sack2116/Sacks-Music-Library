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
                    "file_path": file_path, 
                    "lyrics": lyrics
                })
    return pd.DataFrame(songs)

# Extract metadata (title, album, artist, genre, year, lyrics)
'''def extract_metadata(file_path):
    audio = MP3(file_path, ID3=ID3)
    
    title = audio.tags.get("TIT2", TIT2(encoding=3, text=["Unknown Title"])).text[0]
    album = audio.tags.get("TALB", TALB(encoding=3, text=["Unknown Album"])).text[0]
    artist = audio.tags.get("TPE1", TPE1(encoding=3, text=["Unknown Artist"])).text[0]
    genre = audio.tags.get("TCON", TCON(encoding=3, text=["Unknown Genre"])).text[0]
    year = audio.tags.get("TYER", TYER(encoding=3, text=["Unknown Year"])).text[0]

    lyrics = load_lyrics(file_path)

    return title, album, artist, genre, year, lyrics
'''
def extract_metadata(file_path):
    try:
        audio = MP3(file_path, ID3=ID3)

        title = audio.tags.get("TIT2", TIT2(encoding=3, text=["Unknown Title"])).text[0]
        album = audio.tags.get("TALB", TALB(encoding=3, text=["Unknown Album"])).text[0]
        artist = audio.tags.get("TPE1", TPE1(encoding=3, text=["Unknown Artist"])).text[0]
        genre = audio.tags.get("TCON", TCON(encoding=3, text=["Unknown Genre"])).text[0]

        # Extract year safely (Check both ID3v2 "TDRC" and ID3v1 "TYER")
        year_tag = audio.tags.get("TDRC") or audio.tags.get("TYER")
        year = str(year_tag.text[0]) if year_tag else "Unknown Year"

        # Extract lyrics safely
        lyrics = "No Lyrics Available"
        for tag in audio.tags.values():
            if isinstance(tag, USLT):  # Look for any USLT frame
                lyrics = tag.text
                break  

        return title, album, artist, genre, year, lyrics

    except Exception as e:
        print(f"Error extracting metadata from {file_path}: {e}")
        return "Unknown Title", "Unknown Album", "Unknown Artist", "Unknown Genre", "Unknown Year", "No Lyrics Available"


# Load lyrics from a .txt file with the same name as the MP3
import os
import glob

def load_lyrics(file_path):
    lyrics_dir = os.path.dirname(file_path)  # Get the directory of the MP3 file
    txt_files = glob.glob(os.path.join(lyrics_dir, "*.txt"))  # Find all .txt files in the same folder
    if txt_files:  # If there are any .txt files
        with open(txt_files[0], "r", encoding="utf-8") as f:  # Open the first one found
            return f.read()
    return "No Lyrics Available"  # Default if no .txt files are found

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
    html.H1("🎵Sack' Music Library and Player", style={"text-align": "center", "color": "white"}),
    
    html.Div([
        html.H3("Available Songs", style={"color": "white"}),
        html.Div([
            html.Div([
                html.Img(src=row['artwork'], style={"width": "40px", "height": "40px", "margin-right": "10px"}),
                html.Button(
                    f"{row['title']} - {row['album']} ({row['duration']})",
                    id=f"song-btn-{i}",
                    n_clicks=0,
                    style={
                        "display": "flex",
                        "align-items": "center",
                        "background": "transparent",
                        "color": "white",
                        "border": "none",
                        "width": "100%",
                        "text-align": "left",
                        "cursor": "pointer",
                        "padding": "10px",
                        "font-size": "16px"
                    }
                )
            ], style={
                "display": "flex",
                "align-items": "center",
                "border-bottom": "1px solid gray",
                "padding": "5px",
                "cursor": "pointer"
            }) 
            for i, row in df.iterrows()
        ], id="songs-list", style={"background": "#222", "border-radius": "5px", "padding": "10px"})
    ]),

    html.H3("Now Playing", style={"color": "white"}),
    html.Div([
        html.Img(id="now-playing-artwork", style={"width": "100px", "height": "100px", "margin-bottom": "10px"}),
        html.H2(id="now-playing-title", style={"color": "white"}),
        html.P(id="now-playing-details", style={"color": "gray"})
    ], style={"text-align": "center"}),

    html.Audio(id="audio-player", controls=True, style={"width": "100%"}),

    html.Div([
        html.Button("⏮️ Previous", id="prev-btn", style={"margin-right": "10px"}),
        html.Button("⏭️ Next", id="next-btn", style={"margin-right": "10px"}),
        html.Label("🔊 Volume"),
        dcc.Slider(id="volume-slider", min=0, max=1, step=0.1, value=0.5)
    ], style={"text-align": "center", "margin-top": "10px", "color": "white"}),

    html.H3("Lyrics", style={"color": "white"}),
    html.Div(id="lyrics", style={"white-space": "pre-wrap", "color": "white", "background": "#111", "padding": "10px"})
], style={"background": "#000", "padding": "20px", "height": "100vh", "overflow-y": "scroll"})

# Callback for updating Now Playing & Music Player
@app.callback(
    [Output("now-playing-title", "children"),
     Output("now-playing-artwork", "src"),
     Output("now-playing-details", "children"),
     Output("audio-player", "src"),
     Output("lyrics", "children")],
    [Input(f"song-btn-{i}", "n_clicks") for i in range(len(df))]
)
def update_now_playing(*args):
    ctx = dash.callback_context
    if not ctx.triggered:
        return "Select a Song", "/assets/default_artwork.jpg", "", "", "No Lyrics Available"

    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]

    try:
        song_index = int(triggered_id.split("-")[-1])
    except ValueError:
        return "Select a Song", "/assets/default_artwork.jpg", "", "", "No Lyrics Available"

    selected_song = df.iloc[song_index]
    mp3_file = f"/music/{os.path.relpath(selected_song['file_path'], music_dir)}"

    return (selected_song["title"], 
            selected_song["artwork"], 
            f"Album: {selected_song['album']} | Artist: {selected_song['artist']} | Genre: {selected_song['genre']} | Year: {selected_song['year']}",
            mp3_file,
            selected_song["lyrics"])

# Run Dash app
if __name__ == '__main__':
    app.run_server(debug=True)
