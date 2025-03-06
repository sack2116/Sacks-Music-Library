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

# Format duration (minutes:seconds)
def format_duration(file_path):
    audio = MP3(file_path)
    length = audio.info.length
    minutes = int(length // 60)
    seconds = int(length % 60)
    return f"{minutes}:{seconds:02}"

# Get artwork
def get_artwork_thumbnail(file_path):
    audio = MP3(file_path, ID3=ID3)
    for tag in audio.tags.values():
        if isinstance(tag, APIC):  
            return f"data:image/jpeg;base64,{base64.b64encode(tag.data).decode()}"
    return os.path.join("assets", "default_artwork.jpg")

df = load_songs(MUSIC_DIR)

FAVORITES_FILE = "favorites.json"

def load_favorites():
    if os.path.exists(FAVORITES_FILE):
        with open(FAVORITES_FILE, "r") as f:
            return json.load(f)
    return []

def save_favorites(favorites):
    with open(FAVORITES_FILE, "w") as f:
        json.dump(favorites, f)

favorites = load_favorites()

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

song_list = [
    html.Div([
        html.Img(src=row['artwork'], className="song-artwork"),
        html.Button(
            f"{row['title']} - {row['album']} ({row['duration']})",
            id=f"song-btn-{i}",
            n_clicks=0,
            className="song-button"
        )
    ], className="song-item")
    for i, row in df.iterrows()
]

app.layout = html.Div([
    html.H1([
        html.Span("🎵", style={"color": "#ff66c4", "font-size": "36px", "margin-right": "10px"}),
        "Isaac's Personal Music Library and Player"
    ], style={"text-align": "center"}),

# Songs List & Lyrics Section
html.Div([
    html.Div([
        html.Button("Available Songs 🔽", 
                    id="toggle-dropdown", 
                    className="dropdown-label-button", 
                    n_clicks=0),
        html.Div([
            dcc.Dropdown(
                id="filter-dropdown",
                options=[ 
                    {"label": "All Songs", "value": "all"},
                    {"label": "Favorites ❤️", "value": "favorites"},
                    {"label": "By Album", "value": "by_album"}
                ],
                value="all",
                clearable=False,
                style={"width": "100%", "margin-top": "5px", "display": "none"}  # Hidden by default
            ),
        ], id="dropdown-container")  # Dropdown container wraps dropdown properly
    ], className="song-list", style={"width": "45%"}),  

    html.Div(id="songs-list", className="songs-list-container"),  

    # Lyrics Section
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
        html.Img(id="now-playing-artwork", style={"width": "120px", "height": "120px"}),
        html.H2(id="now-playing-title"),
        html.P(id="now-playing-details"),
                html.Div([
            html.Audio(id="audio-player", controls=True, autoPlay=True, style={"width": "100%", "height": "80px"})
        ], style={
            "border": "2px solid #40E0D0",
            "border-radius": "5px",
            "padding": "10px",
            "width": "100%",
            "margin-top": "10px"
        }),

        html.Div([
            html.Button("⏮️ Previous", id="prev-btn", className="control-button"),
            html.Button("⏭️ Next", id="next-btn", className="control-button")
        ], style={"text-align": "center", "margin-top": "10px"}),

        html.Button("❤️", id="fav-now-playing", n_clicks=0, className="favorite-button")
    ], className="music-player", style={
        "background": "black",
        "border": "2px solid white",
        "border-radius": "10px",
        "padding": "20px",
        "position": "relative",
        "display": "flex",
        "flex-direction": "column",
        "align-items": "center",
        "width": "90%",  # ✅ Match the width of `songs-lyrics-container`
        "margin": "20px auto"
    })
])


favorite_songs = set()
current_song_index = 0

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
@app.callback(
    Output({"type": "favorite-icon", "index": MATCH}, "className"),
    Input({"type": "favorite-button", "index": MATCH}, "n_clicks"),
    State({"type": "favorite-icon", "index": MATCH}, "className"),
    prevent_initial_call=True,
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

def toggle_favorite(n_clicks, class_name):
    song_name = dash.callback_context.triggered[0]["prop_id"].split(".")[0]
    song_name = json.loads(song_name)["index"]
    if song_name in favorites:
        favorites.remove(song_name)
        save_favorites(favorites)
        return "bi bi-heart"
    else:
        favorites.append(song_name)
        save_favorites(favorites)
        return "bi bi-heart-fill text-danger"

def toggle_dropdown(n_clicks, dropdown_style):
    if dropdown_style["display"] == "none":
        dropdown_style["display"] = "block"  # Show dropdown
    else:
        dropdown_style["display"] = "none"   # Hide dropdown
    return dropdown_style

@app.callback(
    Output("filter-dropdown", "style"),
    Input("toggle-dropdown", "n_clicks"),
    State("filter-dropdown", "style"),
    prevent_initial_call=True
)
def toggle_dropdown_callback(n_clicks, dropdown_style):
    return toggle_dropdown(n_clicks, dropdown_style)

@app.callback(
    Output("songs-list", "children"),
    [Input("filter-dropdown", "value")]
)
def filter_songs(filter_value):
    if filter_value == "favorites":
        filtered_songs = df[df["title"].isin(favorite_songs)]
    elif filter_value == "by_album":
        filtered_songs = df.sort_values("album")
    else:
        filtered_songs = df

    return [
        html.Div([
            html.Img(src=song["artwork"], style={"width": "50px", "height": "50px"}),
            html.Button(f"{song['title']} - {song['album']} ({song['duration']})", id=f"song-btn-{i}", className="song-button"),
            html.Button("❤️", id=f"fav-btn-{i}", className="favorite-button", 
                        style={"color": "red" if song["title"] in favorite_songs else "blue"})
        ], className="song-item") for i, song in filtered_songs.iterrows()
    ]

if __name__ == '__main__':
    app.run_server(debug=True)
