#!/bin/bash
# Usage: ./rym-to-spotify.sh <RYM_URL> [--tracks-per-release N]

# Default values
tracks_per_release=1
rym_url=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --tracks-per-release|-t)
            tracks_per_release="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: ./rym-to-spotify.sh <RYM_URL> [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -t, --tracks-per-release N  Tracks to add per album/EP (default: 1)"
            echo "  -h, --help                  Show this help message"
            echo ""
            echo "Example: ./rym-to-spotify.sh https://rateyourmusic.com/list/M4rcus/dream-folk/ -t 3"
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
    echo "Usage: ./rym-to-spotify.sh <RYM_URL> [--tracks-per-release N]"
    echo "Example: ./rym-to-spotify.sh https://rateyourmusic.com/list/M4rcus/dream-folk/"
    exit 1
fi

# Run rym-to-txt.py and capture output
output=$(./rym-to-txt.py "$rym_url")
exit_code=$?

echo "$output"

if [ $exit_code -ne 0 ]; then
    echo "Error: rym-to-txt.py failed"
    exit 1
fi

# Extract filename from output (looks for "written to <filename>")
txt_file=$(echo "$output" | sed -n 's/.*written to \(.*\.txt\)$/\1/p' | tail -1)

if [ -z "$txt_file" ] || [ ! -f "$txt_file" ]; then
    echo "Error: Could not find generated txt file"
    exit 1
fi

echo ""
echo "=== Running txt-to-spotify.py with: $txt_file ==="
echo ""

./txt-to-spotify.py "$txt_file" --tracks-per-release "$tracks_per_release"
