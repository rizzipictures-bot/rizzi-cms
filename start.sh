#!/bin/bash
echo ""
echo "  Rizzi CMS — avvio..."
echo ""
echo "  Sito:  http://localhost:5151/"
echo "  CMS:   http://localhost:5151/cms"
echo ""
echo "  Per fermare: CTRL+C"
echo ""
# Installa dipendenze se mancanti
if ! python3 -c "import flask" 2>/dev/null; then
  echo "  Installazione dipendenze (solo la prima volta)..."
  pip3 install flask pillow -q
fi
# Apri browser dopo 1.5s (apre il sito)
(sleep 1.5 && open "http://localhost:5151/" 2>/dev/null || xdg-open "http://localhost:5151/" 2>/dev/null) &

python3 app.py
