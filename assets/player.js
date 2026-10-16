// Playback and sharing helpers for the music player (Dash loads every .js file in /assets)
(function () {
    let waitingForTap = false;

    function showTapToPlay(show) {
        waitingForTap = show;
        const button = document.getElementById("tap-to-play");
        if (button) button.style.display = show ? "inline-block" : "none";
    }

    // Browsers only allow audio to start by itself after the visitor has interacted with the page.
    // If autoplay is blocked, show "Tap to play" and start on the visitor's first tap or click.
    function tryPlay(audio) {
        const attempt = audio.play();
        if (attempt && attempt.then) {
            attempt.then(() => showTapToPlay(false)).catch((err) => {
                if (err.name === "NotAllowedError") showTapToPlay(true);
            });
        }
    }

    // A new song was loaded into the player: start playing it
    document.addEventListener("loadeddata", (e) => {
        if (e.target.id === "audio-player") tryPlay(e.target);
    }, true);

    document.addEventListener("play", (e) => {
        if (e.target.id === "audio-player") showTapToPlay(false);
    }, true);

    // When a song finishes, go to the next song in the album
    document.addEventListener("ended", (e) => {
        if (e.target.id !== "audio-player") return;
        const next = document.getElementById("next-btn");
        if (next) next.click();
    }, true);

    document.addEventListener("pointerdown", (e) => {
        if (!waitingForTap || e.target.closest("#audio-player")) return;
        const audio = document.getElementById("audio-player");
        if (audio && audio.src) tryPlay(audio);
    }, true);

    function showToast(message) {
        const toast = document.getElementById("toast");
        if (!toast) return;
        toast.textContent = message;
        toast.classList.add("visible");
        clearTimeout(showToast.timer);
        showToast.timer = setTimeout(() => toast.classList.remove("visible"), 2500);
    }

    // Share buttons: phone share sheet on touch devices, otherwise copy the link
    document.addEventListener("click", async (e) => {
        const button = e.target.closest("[data-share-id]");
        if (!button) return;
        const songId = button.getAttribute("data-share-id");
        if (!songId) return;
        const title = button.getAttribute("data-share-title") || "this song";
        const url = `${window.location.origin}/s/${encodeURIComponent(songId)}`;
        if (navigator.share && window.matchMedia("(pointer: coarse)").matches) {
            try {
                await navigator.share({ title: title, text: `Listen to "${title}"`, url: url });
                return;
            } catch (err) {
                if (err.name === "AbortError") return;
            }
        }
        try {
            await navigator.clipboard.writeText(url);
            showToast(`Link to "${title}" copied`);
        } catch (err) {
            window.prompt("Copy this link to share the song:", url);
        }
    });
})();
