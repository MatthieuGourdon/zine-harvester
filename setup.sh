#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "Starting Zine Harvester setup..."

# 1. Create base directory structure
echo "Creating base database and data directories..."
mkdir -p db data/raw data/processed

# 2. Check prerequisites
if ! command -v ia &> /dev/null; then
    echo "Error: 'ia' command not found."
    echo "Please activate your virtualenv and install internetarchive:"
    echo "  source venv/bin/activate && pip install internetarchive"
    exit 1
fi

if ! command -v wget &> /dev/null; then
    echo "Error: 'wget' command not found."
    echo "Please install wget using your package manager (e.g. sudo apt install wget)."
    exit 1
fi

# 3. Define Archive.org sources to download: "identifier|glob_pattern|destination_subfolder"
# Add new zines / collections to this list as needed.
IA_SOURCES=(
    "phrack67|*.txt|data/raw/phrack67"
)

# 4. Define wget HTTP/FTP directory sources: "url|accept_pattern|destination_subfolder"
WGET_SOURCES=(
    "http://textfiles.com/rpg/|txt|data/raw/retro_rpg"
    "http://textfiles.com/magazines/CHEAPTRUTH/|txt|data/raw/cheap_truth"
)

# 5. Download Archive.org sources
for entry in "${IA_SOURCES[@]}"; do
    IFS="|" read -r item_id glob_pattern dest_dir <<< "$entry"

    echo ""
    echo "----------------------------------------------------"
    echo "Fetching (ia) '$item_id' (pattern: $glob_pattern) -> $dest_dir"
    echo "----------------------------------------------------"

    mkdir -p "$dest_dir"
    
    # Download matching files directly into the destination directory
    ia download "$item_id" --glob="$glob_pattern" --destdir="$dest_dir" --no-directories
done

# 6. Download wget sources
for entry in "${WGET_SOURCES[@]}"; do
    IFS="|" read -r url accept_pattern dest_dir <<< "$entry"

    echo ""
    echo "----------------------------------------------------"
    echo "Fetching (wget) '$url' (pattern: $accept_pattern) -> $dest_dir"
    echo "----------------------------------------------------"

    mkdir -p "$dest_dir"

    # -r: recursive, -l1: level 1 depth, -nd: no directories hierarchy, -P: target directory
    wget -r -l1 -nd -q --show-progress -P "$dest_dir" -A "$accept_pattern" "$url" || true
done

echo ""
echo "Setup complete! All raw datasets are downloaded and ready."
