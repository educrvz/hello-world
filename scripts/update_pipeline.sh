#!/bin/bash
# =============================================================
#  SoroJá — Pipeline de Atualização Automatizado
#  Executa: extração → geocodificação → deploy
#
#  Uso: ./scripts/update_pipeline.sh
#  Pré-requisito: PDFs novos já salvos na raiz do projeto
#                 como ESTADO_YYYYMMDD.pdf (ex: AL_20260409.pdf)
# =============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

echo "============================================================"
echo "  SoroJá — Pipeline de Atualização"
echo "============================================================"
echo ""

# ── Step 1: Verify new PDFs exist ─────────────────────────────
echo "📂 Verificando PDFs..."
PDF_COUNT=$(ls -1 *.pdf 2>/dev/null | wc -l | tr -d ' ')
if [ "$PDF_COUNT" -eq 0 ]; then
    echo "❌ Nenhum PDF encontrado na raiz do projeto!"
    echo "   Baixe os PDFs de gov.br e salve aqui: $PROJECT_DIR"
    exit 1
fi
echo "   Encontrados: $PDF_COUNT PDFs"
ls -1 *.pdf 2>/dev/null | while read f; do echo "   • $f"; done
echo ""

# ── Step 2: Check Python dependencies ────────────────────────
echo "🔧 Verificando dependências..."
MISSING=""
python3 -c "import pdfplumber" 2>/dev/null || MISSING="$MISSING pdfplumber"
python3 -c "import geopy" 2>/dev/null || MISSING="$MISSING geopy"

if [ -n "$MISSING" ]; then
    echo "   Instalando dependências faltantes:$MISSING"
    pip3 install $MISSING --quiet
fi
echo "   ✅ Dependências OK"
echo ""

# ── Step 3: Extract hospital data from PDFs ───────────────────
echo "📋 Extraindo dados dos PDFs..."
python3 scripts/extract.py
if [ ! -f hospitals_raw.json ]; then
    echo "❌ Extração falhou — hospitals_raw.json não gerado"
    exit 1
fi
RAW_COUNT=$(python3 -c "import json; print(len(json.load(open('hospitals_raw.json'))))")
echo "   ✅ $RAW_COUNT hospitais extraídos → hospitals_raw.json"
echo ""

# ── Step 4: Geocode addresses ─────────────────────────────────
echo "🌍 Geocodificando endereços (pode levar alguns minutos)..."
echo "   (resultados em cache são reutilizados)"
python3 scripts/geocode.py
if [ ! -f hospitals.json ]; then
    echo "❌ Geocodificação falhou — hospitals.json não gerado"
    exit 1
fi
FINAL_COUNT=$(python3 -c "import json; print(len(json.load(open('hospitals.json'))))")
GEOCODED=$(python3 -c "import json; d=json.load(open('hospitals.json')); print(sum(1 for h in d if h.get('lat')))")
echo "   ✅ $GEOCODED/$FINAL_COUNT hospitais geocodificados"
echo ""

# ── Step 5: Copy to app directory ─────────────────────────────
echo "📦 Copiando hospitals.json para app/..."
cp hospitals.json app/hospitals.json
echo "   ✅ app/hospitals.json atualizado"
echo ""

# ── Step 6: Git commit & push ─────────────────────────────────
echo "🚀 Commitando e fazendo push..."
cd "$PROJECT_DIR"

# Check if there are changes
if git diff --quiet app/hospitals.json 2>/dev/null; then
    echo "   ⚠️  Nenhuma alteração em app/hospitals.json"
    echo "   Os dados já estão atualizados."
else
    # Get list of updated states from git diff
    TODAY=$(date +%Y-%m-%d)
    git add app/hospitals.json
    git commit -m "Atualizar dados hospitalares — $TODAY

Dados extraídos dos PDFs PESA atualizados do Ministério da Saúde.
$FINAL_COUNT hospitais, $GEOCODED geocodificados."

    echo ""
    echo "   Fazendo push para GitHub (deploy automático via Vercel)..."
    git push
    echo "   ✅ Push concluído! Vercel fará deploy automaticamente."
fi

echo ""
echo "============================================================"
echo "  ✅ Pipeline concluído!"
echo "  🌐 Confira em: https://soroja.com.br"
echo "============================================================"
