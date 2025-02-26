window.dash_clientside = Object.assign({}, window.dash_clientside, {
    player: {
        getCurrentTime: function(n_intervals) {
            let audio = document.getElementById("audio-player");
            return audio ? audio.currentTime : 0;
        }
    }
});
