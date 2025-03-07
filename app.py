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
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def save_favorites(favorites):
    with open(FAVORITES_FILE, "w") as f:
        json.dump(favorites, f)

favorites = load_favorites()

app = dash.Dash(__name__, 
                external_stylesheets=[
                    'https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap',
                    '/assets/style.css'
                ],
                meta_tags=[
                    {"name": "viewport", "content": "width=device-width, initial-scale=1.0"}
                ])

server = app.server
app.css.config.serve_locally = True

# Serve music files
@app.server.route("/music/<path:song_path>")
def serve_music(song_path):
    full_path = os.path.abspath(os.path.join(BASE_DIR, song_path))
    if os.path.exists(full_path):
        return send_file(full_path, mimetype="audio/mpeg")
    return "File Not Found", 404

app.layout = html.Div([
    html.H1([
        html.Span("🎵", style={"color": "#ff66c4", "font-size": "36px", "margin-right": "10px"}),
        "Isaac's Personal Music Library and Player"
    ], style={"text-align": "center"}),

    html.Div([
        html.Div([
            html.Div([
                html.Button("Available Songs", 
                        id="toggle-dropdown", 
                        className="dropdown-label-button", 
                        n_clicks=0),
                html.Div([
                    html.Button("Filter Dropdown 🔽", 
                            id="filter-button", 
                            className="filter-dropdown-button"),
                    dcc.Dropdown(
                        id="filter-dropdown",
                        options=[ 
                            {"label": "All Songs", "value": "all"},
                            {"label": "Favorites ❤️", "value": "favorites"},
                            {"label": "By Album", "value": "by_album"}
                        ],
                        value="all",
                        clearable=False,
                        style={"width": "100%", "margin-top": "5px", "display": "none"}
                    ),
                ], id="dropdown-container", className="dropdown-container")  
            ], className="song-list-header"),

            html.Div(id="songs-list", className="songs-list-container"),
        ], className="song-list"),

        # Lyrics Section
        html.Div([
            html.H3("Lyrics", className="section-heading"),
            html.Div(id="lyrics", className="lyrics-content")
        ], className="lyrics-container"),
    ], className="songs-lyrics-container"),

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
        html.Img(id="now-playing-artwork", src="/assets/default_artwork.jpg", style={"width": "120px", "height": "120px"}),
        html.H2(id="now-playing-title", children="Select a Song"),
        html.P(id="now-playing-details", children=""),
        html.Div([
            html.Audio(id="audio-player", controls=True, autoPlay=True, style={"width": "100%", "height": "80px"})
        ], style={
            "border": "2px solid #40E0D0",
            "border-radius": "10px",
            "padding": "10px",
            "width": "100%",
            "margin-top": "10px"
        }),

        html.Div([
            html.Button("⏮️ Previous", id="prev-btn", className="control-button"),
            html.Button("❤️", id="fav-now-playing", n_clicks=0, className="favorite-button"),
            html.Button("⏭️ Next", id="next-btn", className="control-button")
        ], style={"text-align": "center", "margin-top": "20px", "display": "flex", "justify-content": "center", "align-items": "center"}),
        
        # Store components for state management
        dcc.Store(id="current-song-index", data=0),
        dcc.Store(id="favorites-store", data=favorites),
        
        # Add a trigger for initial load
        dcc.Store(id="initial-load-trigger", data=0)
    ], className="music-player")
])

# Generate song list - now responds to initial-load-trigger as well
@app.callback(
    Output("songs-list", "children"),
    [Input("filter-dropdown", "value"),
     Input("favorites-store", "data"),
     Input("initial-load-trigger", "data")]  # Added initial load trigger
)
def generate_song_list(filter_value, favorites, _):
    if filter_value == "favorites":
        filtered_df = df[df['title'].isin(favorites)]
    elif filter_value == "by_album":
        filtered_df = df.sort_values("album")
    else:
        filtered_df = df
    
    songs_list = []
    for i, row in filtered_df.iterrows():
        is_favorite = row['title'] in favorites
        heart_class = "favorite-button active" if is_favorite else "favorite-button"
        
        song_item = html.Div([
            html.Img(src=row['artwork'], className="song-artwork"),
            html.Button(
                f"{row['title']} - {row['album']} ({row['duration']})",
                id={"type": "song-btn", "index": i},
                n_clicks=0,
                className="song-button"
            ),
            html.Button(
                "❤️", 
                id={"type": "fav-btn", "index": i},
                n_clicks=0,
                className=heart_class
            )
        ], className="song-item")
        
        songs_list.append(song_item)
    
    return songs_list

# Toggle dropdown visibility
@app.callback(
    Output("filter-dropdown", "style"),
    Input("filter-button", "n_clicks"),
    State("filter-dropdown", "style"),
    prevent_initial_call=True
)
def toggle_dropdown(n_clicks, dropdown_style):
    if n_clicks:
        dropdown_style = dropdown_style.copy()
        dropdown_style["display"] = "block" if dropdown_style["display"] == "none" else "none"
    return dropdown_style

# Handle song selection and player controls
@app.callback(
    [Output("now-playing-title", "children"),
     Output("now-playing-artwork", "src"),
     Output("now-playing-details", "children"),
     Output("audio-player", "src"),
     Output("lyrics", "children"),
     Output("current-song-index", "data"),
     Output("fav-now-playing", "className")],
    [Input({"type": "song-btn", "index": dash.dependencies.ALL}, "n_clicks"),
     Input("prev-btn", "n_clicks"),
     Input("next-btn", "n_clicks")],
    [State("current-song-index", "data"),
     State("favorites-store", "data")],
    prevent_initial_call=True
)
def update_now_playing(song_clicks, prev_clicks, next_clicks, current_index, favorites):
    ctx = dash.callback_context
    
    if not ctx.triggered:
        return "Select a Song", "/assets/default_artwork.jpg", "", "", "No Lyrics Available", 0, "favorite-button"
    
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
    
    if "song-btn" in triggered_id:
        # Extract the index from the JSON string
        index_dict = json.loads(triggered_id)
        current_index = index_dict["index"]
    elif triggered_id == "prev-btn" and prev_clicks:
        current_index = (current_index - 1) % len(df)
    elif triggered_id == "next-btn" and next_clicks:
        current_index = (current_index + 1) % len(df)
    
    song = df.iloc[current_index]
    song_url = f"/music/{song['file_path']}"
    
    # Check if the current song is a favorite
    is_favorite = song["title"] in favorites
    heart_class = "favorite-button active" if is_favorite else "favorite-button"
    
    return (
        song["title"], 
        song["artwork"], 
        f"Album: {song['album']} | Artist: {song['artist']} | Year: {song['year']} | Length: {song['duration']}",
        song_url,
        song["lyrics"],
        current_index,
        heart_class
    )

# FIX: Update favorite button class without redirecting/changing the song
@app.callback(
    Output({"type": "fav-btn", "index": dash.dependencies.MATCH}, "className"),
    Input({"type": "fav-btn", "index": dash.dependencies.MATCH}, "n_clicks"),
    [State({"type": "fav-btn", "index": dash.dependencies.MATCH}, "className"),
     State("favorites-store", "data"),
     State({"type": "fav-btn", "index": dash.dependencies.MATCH}, "id")],
    prevent_initial_call=True
)
def update_favorite_button_class(n_clicks, current_class, favorites, button_id):
    if not n_clicks:
        return current_class
    
    # Toggle the class
    if "active" in current_class:
        return "favorite-button"
    else:
        return "favorite-button active"


# Separate callback to update the favorites store
@app.callback(
    Output("favorites-store", "data"),
    Input({"type": "fav-btn", "index": dash.dependencies.ALL}, "n_clicks"),
    [State({"type": "fav-btn", "index": dash.dependencies.ALL}, "id"),
     State("favorites-store", "data")],
    prevent_initial_call=True
)
def update_favorites_store(n_clicks_list, button_ids, favorites):
    ctx = dash.callback_context
    if not ctx.triggered:
        return favorites
    
    # Get the button that was clicked
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
    button_idx = json.loads(triggered_id)["index"]
    
    # Find the position in the list that corresponds to this button
    clicked_button_position = None
    for i, button_id in enumerate(button_ids):
        if button_id["index"] == button_idx:
            clicked_button_position = i
            break
    
    if clicked_button_position is None or n_clicks_list[clicked_button_position] == 0:
        return favorites
    
    song_title = df.iloc[button_idx]["title"]
    new_favorites = favorites.copy()
    
    if song_title in new_favorites:
        new_favorites.remove(song_title)
    else:
        new_favorites.append(song_title)
    
    # Save to file
    save_favorites(new_favorites)
    
    return new_favorites

# Handle "favorite now playing" button
@app.callback(
    [Output("fav-now-playing", "className", allow_duplicate=True),
     Output("favorites-store", "data", allow_duplicate=True)],
    Input("fav-now-playing", "n_clicks"),
    [State("current-song-index", "data"),
     State("favorites-store", "data")],
    prevent_initial_call=True
)
def toggle_now_playing_favorite(n_clicks, current_index, favorites):
    if not n_clicks:
        return dash.no_update, dash.no_update
    
    song_title = df.iloc[current_index]["title"]
    new_favorites = favorites.copy()
    
    if song_title in new_favorites:
        new_favorites.remove(song_title)
        new_class = "favorite-button"
    else:
        new_favorites.append(song_title)
        new_class = "favorite-button active"
    
    # Save to file
    save_favorites(new_favorites)
    
    return new_class, new_favorites

if __name__ == '__main__':
    app.run_server(debug=True)
