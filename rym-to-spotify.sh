#!/bin/bash
# Usage: ./rym-to-spotify.sh <RYM_URL>
# Scrapes a RYM list to a text file, then use /build-playlist <file>.txt to create the Spotify playlist.

rym_url=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            echo "Usage: ./rym-to-spotify.sh <RYM_URL>"
            echo ""
            echo "Scrapes a RateYourMusic list to a text file."
            echo "Then use Claude Code's /build-playlist <file>.txt to create the Spotify playlist."
            echo ""
            echo "Example: ./rym-to-spotify.sh https://rateyourmusic.com/list/M4rcus/dream-folk/"
            exit 0
            ;;
        *)
            if [ -z "$rym_url" ]; then
                rym_url="$1"
            fi
            shift
            ;;
    esac
done

if [ -z "$rym_url" ]; then
    echo "Usage: ./rym-to-spotify.sh <RYM_URL>"
    echo "Example: ./rym-to-spotify.sh https://rateyourmusic.com/list/M4rcus/dream-folk/"
    exit 1
fi

./rym-to-txt.py "$rym_url"
