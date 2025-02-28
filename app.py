import os
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
from flask import send_file
import pandas as pd

# Load songs from directory
music_dir = "path/to/your/music"
df = load_songs(music_dir)  # Ensure this function is properly defined elsewhere

# Initialize Dash app
app = dash.Dash(__name__)
server = app.server  

@app.server.route("/music/<path:song_path>")
def serve_music(song_path):
    full_path = os.path.abspath(os.path.join(music_dir, song_path))
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

    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if "song-btn" in triggered_id:
        song_index = int(triggered_id.split("-")[-1])
        current_song_index = song_index
    elif triggered_id == "prev-btn":
        current_song_index = (current_song_index - 1) % len(df)
    elif triggered_id == "next-btn":
        current_song_index = (current_song_index + 1) % len(df)

    selected_song = df.iloc[current_song_index]
    mp3_file = f"/music/{os.path.relpath(selected_song['file_path'], music_dir)}"

    return (selected_song["title"], 
            selected_song["artwork"], 
            f"Album: {selected_song['album']} | Artist: {selected_song['artist']} | Genre: {selected_song['genre']} | Year: {selected_song['year']}",
            mp3_file, 
            selected_song["lyrics"])

if __name__ == '__main__':
    app.run_server(debug=True)
