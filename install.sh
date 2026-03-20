#!/bin/bash
# ─────────────────────────────────────────────
#  SceneDetect for Final Cut Pro — Instalação
# ─────────────────────────────────────────────

set -e

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  SceneDetect for Final Cut Pro           ║"
echo "║  Instalação automática                   ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── Verifica Python ───────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "❌  Python 3 não encontrado."
    echo "    Instale em: https://www.python.org/downloads/"
    exit 1
fi
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "✅  Python $PYTHON_VERSION encontrado"

# ── Verifica / instala python-tk ──────────────
if ! python3 -c "import _tkinter" &>/dev/null; then
    echo "📥  Instalando python-tk@$PYTHON_VERSION via Homebrew…"
    brew install "python-tk@$PYTHON_VERSION"
else
    echo "✅  python-tk encontrado"
fi

# ── Verifica Homebrew ─────────────────────────
if ! command -v brew &>/dev/null; then
    echo ""
    echo "❌  Homebrew não encontrado (necessário para instalar o FFmpeg)."
    echo "    Instale com:"
    echo '    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    echo ""
    echo "    Depois rode ./install.sh novamente."
    exit 1
fi
echo "✅  Homebrew encontrado"

# ── Verifica / instala FFmpeg ─────────────────
if ! command -v ffmpeg &>/dev/null; then
    echo "📥  Instalando FFmpeg via Homebrew…"
    brew install ffmpeg
else
    FFMPEG_VERSION=$(ffmpeg -version 2>&1 | head -1 | awk '{print $3}')
    echo "✅  FFmpeg $FFMPEG_VERSION encontrado"
fi

# ── Cria venv ─────────────────────────────────
if [ ! -d "venv" ]; then
    echo "📦  Criando ambiente virtual…"
    python3 -m venv venv
fi
source venv/bin/activate

# ── Instala dependências Python ───────────────
echo "📥  Instalando dependências Python…"
pip install --quiet --upgrade pip
pip install --quiet "scenedetect[opencv]" customtkinter

echo ""
echo "✅  Instalação concluída!"
echo ""
echo "Para iniciar o app:"
echo "   ./run.sh"
echo ""
