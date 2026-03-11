Given the RYM chart URL `$ARGUMENTS`, create a Spotify playlist containing **all tracks from every album** on the chart, in chart order, with tracks in album order.

## Step 1: Scrape the chart

Run `./rym-to-txt.py $ARGUMENTS` via bash. The `$ARGUMENTS` may include `--pages N` to limit scraping to N pages. This outputs a `.txt` file. The filename is printed in the last line of output (e.g. "... written to SomeChart.txt"). Capture that filename.

## Step 2: Read and parse the output file

- Line 1: `title: "Chart Name"` — use as the playlist name
- Line 2: `url: "..."` — skip
- Remaining lines have the format: `album: "Album" - "Artist" [spotify:ID]` (the `[spotify:ID]` part is optional; the type prefix may also be `ep:`, `single:`, `compilation:`, etc.)
- Parse out the album name, artist name, and optional Spotify album ID from each line

## Step 2.5: Configure request pacing

Parse optional `--window HOURS` from `$ARGUMENTS` (e.g. `--window 2` means spread work over 2 hours).

If `--window` is present:
1. Count how many albums were parsed (`albumCount`)
2. Estimate total Spotify API calls: assume ~2 calls per album without a Spotify ID (search + getAlbumTracks), ~1 call per album with an ID, plus `ceil(albumCount × 10 / 100)` calls to add tracks in batches, plus 1 for createPlaylist. Use: `estimatedCalls = albumCount * 2 + ceil(albumCount * 10 / 100) + 1`
3. Calculate: `delayMs = floor(windowHours * 3600 * 1000 / estimatedCalls)`
4. Clamp to [350, 300000] ms range
5. Call `setRequestDelay` with the computed value
6. Log: "Pacing: ~N estimated calls over H hours, ~Xs between requests"

If `--window` is not provided, leave the default (350ms).

## Step 3: For each album, get all tracks from Spotify

For each album entry, in order:

1. **If a Spotify ID is present** (from `[spotify:ID]`): call `getAlbumTracks` directly with that ID
2. **If no Spotify ID**: call `searchSpotify` with type `album` and query `artist:ARTIST album:ALBUM` to find the album. If no results, try a simpler query `ARTIST ALBUM`. Extract the album ID from the first result, then call `getAlbumTracks`.
3. Collect all track URIs in album track-number order.
4. If an album has more than 50 tracks, paginate using the `offset` parameter (fetch 50 at a time).
5. If an album can't be found, log it and continue.

## Step 4: Create the playlist and add tracks

1. Call `createPlaylist` with the chart title as the name.
2. Call `addTracksToPlaylist` with the collected track URIs, in batches of 100 max.

## Step 5: Print summary

Report:
- Total albums processed vs. total on chart
- Total tracks added
- List of albums that couldn't be found (if any)
- The playlist URL

## Important
- Do NOT stop on individual failures — skip and continue
- Process album lookups sequentially to avoid rate limiting
- Preserve chart order (album-by-album) and track order within each album
