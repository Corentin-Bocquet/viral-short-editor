#!/bin/bash

# ==================================================
# VIRAL SHORT EDITOR - ONE-CLICK LAUNCHER
# ==================================================

set -e  # Exit on error

echo "======================================"
echo " 📱 Viral Short Editor Launcher"
echo "======================================"
echo ""

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 n'est pas installé"
    echo "Télécharge Python 3.11+ sur: https://www.python.org/downloads/"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d ' ' -f 2 | cut -d '.' -f 1,2)
echo "✓ Python $PYTHON_VERSION détecté"

# Check FFmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo ""
    echo "⚠️  FFmpeg n'est pas installé"
    echo "   L'app ne pourra pas traiter les vidéos sans FFmpeg."
    echo ""
    echo "Installation rapide:"
    echo "   - macOS: brew install ffmpeg"
    echo "   - Ubuntu/Debian: sudo apt install ffmpeg"
    echo "   - Windows: https://ffmpeg.org/download.html"
    echo ""
    read -p "Continuer quand même ? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "✓ FFmpeg installé"
fi

# Create virtual environment if not exists
if [ ! -d "venv" ]; then
    echo ""
    echo "📦 Création de l'environnement virtuel..."
    python3 -m venv venv
    echo "✓ Environnement créé"
fi

# Activate virtual environment
echo ""
echo "🔄 Activation de l'environnement..."
source venv/bin/activate || . venv/Scripts/activate

# Install/update dependencies
echo ""
echo "📥 Installation des dépendances..."
pip install -q --upgrade pip
pip install -q -r backend/requirements.txt

echo "✓ Dépendances installées"

# Check Whisper (optional)
if python3 -c "import whisper" 2>/dev/null; then
    echo "✓ Whisper installé (sous-titres actifs)"
else
    echo "⚠️  Whisper non installé (sous-titres désactivés)"
    echo "   Pour activer: pip install openai-whisper"
fi

# Check Pexels API key (optional)
if [ -f ".env" ]; then
    if grep -q "PEXELS_API_KEY" .env; then
        echo "✓ Clé Pexels détectée (B-rolls actifs)"
    else
        echo "⚠️  Pas de clé Pexels (B-rolls désactivés)"
        echo "   Pour activer: crée un fichier .env avec PEXELS_API_KEY=ta_cle"
    fi
else
    echo "⚠️  Fichier .env absent (B-rolls désactivés)"
fi

echo ""
echo "======================================"
echo " 🚀 Lancement de l'application"
echo "======================================"
echo ""
echo "Backend API: http://localhost:8000"
echo "Interface web: http://localhost:8000 (ouvre automatiquement)"
echo ""
echo "Appuie sur Ctrl+C pour arrêter"
echo ""

# Start backend
cd backend

# Open browser after 2 seconds (background)
(sleep 2 && python3 -m webbrowser http://localhost:8000) &

# Run server
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
