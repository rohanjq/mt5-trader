#!/usr/bin/env bash
# Collect EA diagnostic dumps + download recent bars into the repo.
# Run on the remote (where MT5 is running) after ~20 min.
#
# Usage:
#   ./scripts/collect_ea_data.sh
#
# What it does:
#   1. Copies EA trail dump CSVs from Common/Files/dumps/ into sampledata/ea_dumps/
#   2. Copies current signal CSVs (snapshot) into sampledata/ea_dumps/signals/
#   3. Downloads 30 min of bars for all TFs
#   4. Commits and pushes

set -e
cd "$(dirname "$0")/.."

# --- Paths ---
# MT5 Common/Files is typically symlinked here in the docker setup
COMMON_FILES="../MetaTrader5-Docker/data/signals"
# Alternative path (direct Wine path)
WINE_COMMON="/root/.wine/drive_c/users/root/AppData/Roaming/MetaQuotes/Terminal/Common/Files"

# Find where the EA files actually are
if [ -d "$COMMON_FILES/dumps" ]; then
    DUMPS_SRC="$COMMON_FILES/dumps"
    SIGNALS_SRC="$COMMON_FILES"
elif [ -d "$WINE_COMMON/dumps" ]; then
    DUMPS_SRC="$WINE_COMMON/dumps"
    SIGNALS_SRC="$WINE_COMMON"
else
    echo "ERROR: Cannot find EA dumps directory."
    echo "Checked: $COMMON_FILES/dumps"
    echo "Checked: $WINE_COMMON/dumps"
    echo ""
    echo "Looking for any dumps files..."
    find / -name "XAUUSD_utbot_trail_FULL*" 2>/dev/null | head -5
    exit 1
fi

echo "Found EA dumps at: $DUMPS_SRC"
echo "Found signals at: $SIGNALS_SRC"

# --- 1. Copy trail dumps ---
mkdir -p sampledata/ea_dumps
cp -v "$DUMPS_SRC"/*.csv sampledata/ea_dumps/ 2>/dev/null || echo "No trail dump CSVs found in $DUMPS_SRC"

# --- 2. Copy current signal CSVs (snapshot of all indicators) ---
mkdir -p sampledata/ea_dumps/signals
for f in "$SIGNALS_SRC"/XAUUSD_*.csv; do
    [ -f "$f" ] || continue
    # Skip the dumps subdir files
    cp -v "$f" sampledata/ea_dumps/signals/
done

# --- 3. Download 30 min of bars ---
echo ""
echo "=== Downloading recent bars (last 30 min) ==="
uv run python scripts/download_bars.py \
    --symbol XAUUSD \
    --days 1 \
    --config config-gold.yaml \
    --output sampledata/ea_dumps/bars_recent

# --- 4. Git add, commit, push ---
echo ""
echo "=== Committing and pushing ==="
git add sampledata/ea_dumps/
git commit -m "data: EA diagnostic trail dumps + signal snapshots + recent bars"
git push

echo ""
echo "Done! Data is pushed. Tell copilot to pull."
