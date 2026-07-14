#!/bin/bash
set -e

REPO_URL="https://github.com/INRB-UMIE/BDBV2026-Data.git"
REPO_DIR="BDBV2026-Data"

echo "🧹 Preparing local directories..."
rm -rf data_test
mkdir -p data_test

echo "🚀 Cloning BDBV2026-Data Repository..."
rm -rf "$REPO_DIR"
git clone "$REPO_URL"

echo "🎯 Harvesting only PROCESSED INSP SitRep data..."
# This finds files specifically inside the insp_sitrep processed folder and copies them
TARGET_DIR="$REPO_DIR/data/insp_sitrep/processed"

if [ -d "$TARGET_DIR" ]; then
    echo "✔ Found processed directory. Copying CSVs..."
    find "$TARGET_DIR" -name "*.csv" -exec cp {} data_test/ \;
else
    echo "⚠️ Target directory $TARGET_DIR not found. Searching fallback..."
    find "$REPO_DIR" -path "*/insp_sitrep/processed/*.csv" -exec cp {} data_test/ \;
fi

# Final validation
FINAL_COUNT=$(ls -1 data_test/*.csv 2>/dev/null | wc -l)
if [ "$FINAL_COUNT" -gt 0 ]; then
    echo "✔ Clean copy complete! $FINAL_COUNT processed INSP SitRep CSVs loaded into data_test/."
else
    echo "❌ ERROR: No processed CSV files found for insp_sitrep." >&2
    exit 1
fi
