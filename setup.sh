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

# 3. Define Archive.org sources to download: "identifier|glob_pattern|destination_subfolder"
# Add new zines / collections to this list as needed.
SOURCES=(
    "phrack67|*.txt|data/raw/phrack67"
    # Future examples:
    # "2600magazine|*.txt|data/raw/2600"
    # "cdc_cult_of_the_dead_cow|*.txt|data/raw/cdc"
)

# 4. Download sources
for entry in "${SOURCES[@]}"; do
    IFS="|" read -r item_id glob_pattern dest_dir <<< "$entry"

    echo ""
    echo "----------------------------------------------------"
    echo "Fetching '$item_id' (pattern: $glob_pattern) -> $dest_dir"
    echo "----------------------------------------------------"

    mkdir -p "$dest_dir"
    
    # Download matching files directly into the destination directory
    ia download "$item_id" --glob="$glob_pattern" --destdir="$dest_dir" --no-directories
done

echo ""
echo "Setup complete! All raw datasets are downloaded and ready."
