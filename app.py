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
server = app.server  # Keeping original code intact


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
                    {"label": "Favorites", "value": "favorites"},
                    {"label": "By Album", "value": "by_album"}
                ],
                value="all",
                clearable=False,
                style={ 
                    "width": "auto",
                    "display": "inline-block",
                    "background-color": "rgba(173, 216, 230, 0.8)",  # Light Transparent Blue
                    "color": "black",
                    "border": "1px solid black",
                    "margin-left": "10px",
                    "max-width": "120px"  # Adjust to fit the longest label (e.g., "Favorites")
                }
            )
        ], style={"text-align": "right", "margin-bottom": "10px", "width": "100%"}),

        html.Div([ 
            # Available Songs Section
            html.Div([
                html.H3("Available Songs", className="section-heading"),
                html.Div(id="songs-list", className="songs-list-container")
            ], className="song-list", style={"width": "45%"}),  # 45% width

            # Lyrics Section
            html.Div([
                html.H3("Lyrics", className="section-heading"),
                html.Div(id="lyrics", className="lyrics-container")
            ], className="lyrics-container", style={"width": "45%"})  # 45% width
        ], className="songs-lyrics-container", style={ 
            "display": "flex",
            "justify-content": "space-between",
            "width": "90%",
            "margin": "auto"
        })
    ]),

    html.Div([ 
        html.H3("Now Playing", className="section-heading now-playing-button"),

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
                    "margin-top": "-80px",
                    "right": "20px",
                    "z-index": "5"
                }
            )
        ], style={"position": "relative", "width": "100%", "text-align": "right"}),

        html.Img(id="now-playing-artwork", style={"width": "120px", "height": "120px", "border-radius": "10px"}),
        html.H2(id="now-playing-title"),
        html.P(id="now-playing-details"),

        html.Div([ 
            html.Audio(id="audio-player", controls=True, autoPlay=True, style={"width": "90%", "height": "80px"})
        ], style={ 
            "border": "2px solid #40E0D0",
            "border-radius": "5px",
            "padding": "10px",
            "width": "90%",
            "margin-top": "10px"
        }),

        html.Div([ 
            html.Button("⏮️ Previous", id="prev-btn", className="control-button"),
            html.Button("⏭️ Next", id="next-btn", className="control-button")
        ], style={"text-align": "center", "margin-top": "10px"}),

        html.Button("❤️", id="fav-now-playing", n_clicks=0, className="favorite-button", style={"font-size": "24px"})
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

# Initialize favorite songs set globally
favorite_songs = set()

# Load lyrics function (PartA)
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

    # Load lyrics using the provided function
    lyrics_text = load_lyrics(song["file_path"])

    return (song["title"], 
            song["artwork"], 
            f"Album: {song['album']} | Artist: {song['artist']} | Year: {song['year']} | Length: {song['duration']}",
            song_url,
            lyrics_text)  # Load lyrics using the function

# Callback for the filter dropdown
@app.callback(
    Output("songs-list", "children"),
    [Input("filter-dropdown", "value")]
)
def filter_songs(filter_value):
    if filter_value == "favorites":
        filtered_songs = df[df["title"].isin(favorite_songs)]
    elif filter_value == "by_album":
        # Sorting by album
        filtered_songs = df.sort_values("album")
    else:
        filtered_songs = df

    return [
        html.Div([ 
            html.Button(song["title"], id=f"song-btn-{i}", className="song-button"),
            html.Button("❤️", id=f"fav-btn-{i}", n_clicks=0, className="favorite-button", 
                        style={"color": "red" if song["title"] in favorite_songs else "blue"}),
            html.Div([
                html.Img(src=song["artwork"], alt="Artwork", style={"width": "50px", "height": "50px"}),
                html.P(song["title"]),
                html.P(song["album"]),
                html.P(song["duration"])
            ], style={"display": "flex", "align-items": "center"})
        ], className="song-item") for i, song in filtered_songs.iterrows()
    ]

@app.callback(
    Output("fav-now-playing", "style"),
    [Input("fav-now-playing", "n_clicks")],
    prevent_initial_call=True
)
def toggle_favorite(n_clicks):
    global favorite_songs  # ✅ Ensure global access

    song = df.iloc[current_song_index]["title"]

    if song in favorite_songs:
        favorite_songs.remove(song)
        return {"color": "blue"}  # Unfavorite
    else:
        favorite_songs.add(song)
        return {"color": "red"}  # Mark as favorite

if __name__ == '__main__':
    app.run_server(debug=True)
