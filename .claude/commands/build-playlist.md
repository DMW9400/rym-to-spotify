Read the track list file at $ARGUMENTS (one "Artist - Track" per line, with a playlist name on the first line prefixed with "# ").

Using the Spotify MCP tools, do the following:

1. Parse the file: the first line (after removing "# ") is the playlist name. Each subsequent non-empty line is a track in "Artist - Track" format.

2. Search for each track using `searchSpotify` with type "track". Use the query format "artist:ARTIST track:TRACK". If no result is found, try a simpler query with just "ARTIST TRACK". Log any tracks that couldn't be found.

3. Once you have collected all track IDs, create a new playlist using `createPlaylist` with the parsed playlist name.

4. Add tracks to the playlist using `addTracksToPlaylist` in batches of 100 (the API limit).

5. Print a summary: total tracks found, tracks not found (list them), and the playlist URL.

Important:
- Do NOT stop on individual search failures — skip and continue
- Process searches sequentially to avoid rate limiting
- If the file doesn't exist, tell the user and stop
