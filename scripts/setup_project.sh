#!/bin/bash

set -e

echo "================================="
echo "aimsktt_viralwatch2 ML Project Setup"
echo "================================="


PROJECT_DIR=$(pwd)


echo "[1/6] Creating directories..."

mkdir -p data/raw/who_pdfs
mkdir -p data/external
mkdir -p data/processed
mkdir -p models
mkdir -p reports
mkdir -p notebooks
mkdir -p src
mkdir -p tests


echo "[2/6] Cloning INRB-UMIE/BDBV2026-Data..."

if [ ! -d "data/external/BDBV2026-Data" ]; then

git clone \
https://github.com/INRB-UMIE/BDBV2026-Data.git \
data/external/BDBV2026-Data

else

echo "Repository already exists"

fi


echo "[3/6] Downloading WHO Disease Outbreak News PDFs..."


curl -L \
"https://www.who.int/emergencies/disease-outbreak-news" \
-o data/raw/who_pdfs/who_outbreak_page.html



echo "[4/6] Checking downloaded files..."

FILE="data/raw/who_pdfs/who_outbreak_page.html"


if [ -s "$FILE" ]
then
    echo "Download successful"
else
    echo "Download failed"
    exit 1
fi



echo "[5/6] Creating Python virtual environment..."

python3 -m venv .venv


echo "[6/6] Installing Python packages..."

source .venv/bin/activate


python -m pip install --upgrade pip


pip install -r requirements.txt


echo ""
echo "================================="
echo "Setup completed successfully"
echo "================================="