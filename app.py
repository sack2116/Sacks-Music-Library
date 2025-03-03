import os
import base64
import pandas as pd
import dash
from dash import html, dcc, Output, Input
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TALB, TPE1, TCON, TYER, USLT, APIC
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
                    "lyrics": lyrics,
                    "favorite": False
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

df = load_songs(MUSIC_DIR)

# Initialize Dash app
app = dash.Dash(__name__, external_stylesheets=["/assets/style.css"])
server = app.server

app.layout = html.Div([
    html.H1("Isaac's Personal Music Library and Player", style={"text-align": "center"}),

    # Filter Dropdown
    dcc.Dropdown(
        id="filter-dropdown",
        options=[
            {"label": "All Songs", "value": "all"},
            {"label": "By Album", "value": "album"},
            {"label": "Favorites", "value": "favorites"}
        ],
        value="all",
        clearable=False,
        style={"width": "50%", "margin": "auto"}
    ),

    # Songs & Lyrics Section
    html.Div([
        html.Div([
            html.H3("Available Songs"),
            html.Div(id="songs-list", className="songs-list-container")
        ], className="song-list", style={"width": "45%"}),

        html.Div([
            html.H3("Lyrics"),
            html.Div(id="lyrics", className="lyrics-container")
        ], className="lyrics-container", style={"width": "45%"})
    ], className="songs-lyrics-container", style={"display": "flex", "justify-content": "space-between", "width": "90%", "margin": "auto"}),

    # Now Playing Section
    html.Div([
        html.H3("Now Playing"),
        html.Video(
            id="background-video",
            src="/assets/Sacks.mp4",
            autoPlay=True,
            loop=True,
            muted=True,
            controls=False,
            style={"width": "310px", "height": "270px", "border-radius": "10px", "position": "absolute", "top": "-60px", "right": "20px", "z-index": "5"}
        ),
        html.Img(id="now-playing-artwork", style={"width": "120px", "height": "120px", "margin-top": "20px", "border-radius": "10px", "display": "block"}),
        html.H2(id="now-playing-title", style={"font-size": "20px", "color": "white", "text-align": "center"}),
        html.P(id="now-playing-details", style={"color": "white", "text-align": "center"}),
        html.Audio(id="audio-player", controls=True, autoPlay=True, style={"width": "100%", "height": "80px"})
    ], className="music-player", style={"background": "black", "border": "2px solid white", "border-radius": "10px", "padding": "20px", "width": "90%", "margin": "20px auto"})
])

# Callbacks
@app.callback(
    Output("songs-list", "children"),
    [Input("filter-dropdown", "value")]
)
def update_song_list(filter_value):
    filtered_df = df
    if filter_value == "favorites":
        filtered_df = df[df["favorite"]]
    elif filter_value == "album":
        filtered_df = df.sort_values(by="album")

    return [
        html.Div([
            html.Img(src=row['artwork'], className="song-artwork"),
            html.Button(f"{row['title']} - {row['album']} ({row['duration']})", id=f"song-btn-{i}", n_clicks=0, className="song-button"),
            html.Button("❤️", id=f"fav-btn-{i}", n_clicks=0, className="fav-button" if row["favorite"] else "unfav-button")
        ], className="song-item")
        for i, row in filtered_df.iterrows()
    ]

@app.callback(
    Output("now-playing-title", "children"),
    Output("now-playing-artwork", "src"),
    Output("now-playing-details", "children"),
    Output("audio-player", "src"),
    Output("lyrics", "children"),
    [Input(f"song-btn-{i}", "n_clicks") for i in range(len(df))]
)
def update_now_playing(*clicks):
    ctx = dash.callback_context
    if not ctx.triggered:
        return "Select a Song", "/assets/default_artwork.jpg", "", "", "No Lyrics Available"

    song_index = int(ctx.triggered[0]["prop_id"].split("-")[-1])
    song = df.iloc[song_index]
    song_url = f"/music/{song['file_path']}"

    return song["title"], song["artwork"], f"Album: {song['album']} | Artist: {song['artist']} | Genre: {song['genre']} | Year: {song['year']}", song_url, song["lyrics"]

@app.callback(
    Output("songs-list", "children"),
    [Input(f"fav-btn-{i}", "n_clicks") for i in range(len(df))]
)
def toggle_favorite(*clicks):
    ctx = dash.callback_context
    if ctx.triggered:
        song_index = int(ctx.triggered[0]["prop_id"].split("-")[-1])
        df.at[song_index, "favorite"] = not df.at[song_index, "favorite"]
    return update_song_list("all")

if __name__ == '__main__':
    app.run_server(debug=True)
