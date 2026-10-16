// Static music player: albums, favorites (saved in this browser), Previous / Next within the album,
// autoplay with a "Tap to play" fallback, and share links. The song list comes from build_static.py.
(function () {
    const library = JSON.parse(document.getElementById("library-data").textContent);
    const songsById = {};
    const albumsByKey = {};
    library.albums.forEach((album) => {
        albumsByKey[album.key] = album;
        album.songs.forEach((song) => { songsById[song.id] = song; });
    });

    const audio = document.getElementById("audio-player");
    const albumsView = document.getElementById("albums-view");
    const favoritesView = document.getElementById("favorites-view");
    let currentId = null;
    const openAlbums = new Set();

    // ---- Favorites (stored per browser) ----
    const FAVORITES_KEY = "sacks-music-favorites";
    function loadFavorites() {
        try {
            return new Set(JSON.parse(localStorage.getItem(FAVORITES_KEY)) || []);
        } catch (err) {
            return new Set();
        }
    }
    const favorites = loadFavorites();
    function saveFavorites() {
        try {
            localStorage.setItem(FAVORITES_KEY, JSON.stringify([...favorites]));
        } catch (err) { /* private browsing: favorites last until the page closes */ }
    }
    function toggleFavorite(songId) {
        if (favorites.has(songId)) favorites.delete(songId); else favorites.add(songId);
        saveFavorites();
        refreshHearts();
        renderFavorites();
    }

    // ---- Share links ----
    function shareUrl(songId) {
        return new URL(`s/${encodeURIComponent(songId)}/`, window.location.href).href;
    }

    // ---- Building the lists ----
    function el(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    function songRow(song, number, listType) {
        const row = el("div", "song-item");
        const play = el("button", "song-button");
        play.dataset.songId = song.id;
        if (listType === "album") play.append(el("span", "track-num", `${number}.`));
        play.append(el("span", "song-title", song.title));
        if (listType === "favorites") play.append(el("span", "song-album", song.album));
        play.append(el("span", "song-duration", song.duration));
        play.addEventListener("click", () => selectSong(song.id));

        const heart = el("button", "favorite-button", "❤️");
        heart.title = "Favorite";
        heart.dataset.heartFor = song.id;
        heart.addEventListener("click", () => toggleFavorite(song.id));

        const share = el("button", "share-button", "🔗");
        share.title = "Share this song";
        share.dataset.shareUrl = shareUrl(song.id);
        share.dataset.shareTitle = song.title;

        row.append(play, heart, share);
        return row;
    }

    function renderAlbums() {
        library.albums.forEach((album) => {
            const section = el("div", "album");
            const header = el("button", "album-header");
            header.dataset.album = album.key;
            if (album.cover) {
                const cover = el("img", "album-cover");
                cover.src = album.cover;
                cover.alt = "";
                header.append(cover);
            } else {
                header.append(el("div", "album-cover album-cover-placeholder", "💿"));
            }
            const info = el("div", "album-info");
            info.append(el("div", "album-name", album.name),
                        el("div", "album-meta", `${album.songs.length} song${album.songs.length === 1 ? "" : "s"}`));
            header.append(info, el("span", "album-chevron", "▸"));
            header.addEventListener("click", () => {
                if (openAlbums.has(album.key)) openAlbums.delete(album.key); else openAlbums.add(album.key);
                refreshAlbums();
            });

            const list = el("div", "album-songs");
            list.dataset.albumSongs = album.key;
            album.songs.forEach((song, i) => list.append(songRow(song, i + 1, "album")));
            section.append(header, list);
            albumsView.append(section);
        });
    }

    function renderFavorites() {
        favoritesView.replaceChildren();
        const favoriteSongs = library.albums.flatMap((a) => a.songs).filter((s) => favorites.has(s.id));
        if (!favoriteSongs.length) {
            favoritesView.append(el("p", "empty-message", "No favorites yet. Tap ❤️ on a song to add it here."));
        }
        favoriteSongs.forEach((song, i) => favoritesView.append(songRow(song, i + 1, "favorites")));
        refreshHearts();
        refreshPlaying();
    }

    function refreshAlbums() {
        document.querySelectorAll("[data-album-songs]").forEach((list) => {
            list.style.display = openAlbums.has(list.dataset.albumSongs) ? "block" : "none";
        });
        document.querySelectorAll(".album-header").forEach((header) => {
            header.classList.toggle("open", openAlbums.has(header.dataset.album));
        });
    }

    function refreshHearts() {
        document.querySelectorAll("[data-heart-for]").forEach((heart) => {
            heart.classList.toggle("active", favorites.has(heart.dataset.heartFor));
        });
        document.getElementById("fav-now-playing").classList.toggle("active", favorites.has(currentId));
    }

    function refreshPlaying() {
        document.querySelectorAll(".song-button[data-song-id]").forEach((button) => {
            button.classList.toggle("playing", button.dataset.songId === currentId);
        });
    }

    // ---- Playing ----
    function selectSong(songId) {
        const song = songsById[songId];
        if (!song) return;
        currentId = songId;
        document.getElementById("now-playing-title").textContent = song.title;
        document.getElementById("now-playing-artwork").src = song.art || "";
        document.getElementById("now-playing-details").textContent =
            `Album: ${song.album} | Artist: ${song.artist} | Year: ${song.year} | Length: ${song.duration}`;
        document.getElementById("lyrics").textContent = song.lyrics;
        const share = document.getElementById("share-now-playing");
        share.dataset.shareUrl = shareUrl(song.id);
        share.dataset.shareTitle = song.title;
        document.title = `${song.title} - ${library.siteTitle}`;
        audio.src = song.audio;
        tryPlay();
        openAlbums.add(song.album_key);
        refreshAlbums();
        refreshHearts();
        refreshPlaying();
    }

    // Previous / Next move within the album of the playing song
    function step(direction) {
        const song = songsById[currentId];
        if (!song) return;
        const songs = albumsByKey[song.album_key].songs;
        const position = songs.findIndex((s) => s.id === currentId);
        selectSong(songs[(position + direction + songs.length) % songs.length].id);
    }

    // Browsers only allow audio to start by itself after the visitor has interacted with the page.
    // If autoplay is blocked, show "Tap to play" and start on the visitor's first tap or click.
    let waitingForTap = false;
    function showTapToPlay(show) {
        waitingForTap = show;
        document.getElementById("tap-to-play").style.display = show ? "inline-block" : "none";
    }
    function tryPlay() {
        const attempt = audio.play();
        if (attempt && attempt.then) {
            attempt.then(() => showTapToPlay(false)).catch((err) => {
                if (err.name === "NotAllowedError") showTapToPlay(true);
            });
        }
    }
    audio.addEventListener("play", () => showTapToPlay(false));
    audio.addEventListener("ended", () => step(1));
    document.addEventListener("pointerdown", (e) => {
        if (waitingForTap && !e.target.closest("#audio-player")) tryPlay();
    }, true);

    // ---- Share buttons: phone share sheet on touch devices, otherwise copy the link ----
    function showToast(message) {
        const toast = document.getElementById("toast");
        toast.textContent = message;
        toast.classList.add("visible");
        clearTimeout(showToast.timer);
        showToast.timer = setTimeout(() => toast.classList.remove("visible"), 2500);
    }
    document.addEventListener("click", async (e) => {
        const button = e.target.closest("[data-share-url]");
        if (!button) return;
        const url = button.dataset.shareUrl;
        const title = button.dataset.shareTitle || "this song";
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

    // ---- Controls ----
    document.getElementById("prev-btn").addEventListener("click", () => step(-1));
    document.getElementById("next-btn").addEventListener("click", () => step(1));
    document.getElementById("fav-now-playing").addEventListener("click", () => {
        if (currentId) toggleFavorite(currentId);
    });
    document.querySelectorAll("[data-view]").forEach((tab) => {
        tab.addEventListener("click", () => {
            const showFavorites = tab.dataset.view === "favorites";
            albumsView.hidden = showFavorites;
            favoritesView.hidden = !showFavorites;
            document.querySelectorAll("[data-view]").forEach((t) => t.classList.toggle("selected", t === tab));
        });
    });

    // ---- Start: the shared song (?song=<id>) or the featured song ----
    renderAlbums();
    renderFavorites();
    const requested = new URLSearchParams(window.location.search).get("song");
    selectSong(songsById[requested] ? requested : library.featured);
})();
