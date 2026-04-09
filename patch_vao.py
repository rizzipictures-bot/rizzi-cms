#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sostituisce il blocco VIEW ALL OVERLAY IIFE con la versione aggiornata."""

with open('static/site/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

start_marker = '// VIEW ALL OVERLAY \u2014 stile Miechowski'
end_marker = '// CITIES THUMBNAIL \u2014 RAF loop per lerp continuo'

start_idx = content.find(start_marker)
end_idx   = content.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print('MARKER NON TROVATI')
    exit(1)

new_block = r"""// VIEW ALL OVERLAY — stile Miechowski
// ══════════════════════════════════════════════════════════════
(function() {
  const overlay      = document.getElementById('archive-viewall-overlay');
  const vaoTitle     = document.getElementById('vao-title');
  const vaoClose     = document.getElementById('vao-close');
  const vaoGrid      = document.getElementById('vao-grid');
  const vaoThemeBtn  = document.getElementById('vao-theme-toggle');
  // Viewer singolo interno al VAO
  const vaoViewer    = document.getElementById('vao-viewer');
  const vaoViewerImg = document.getElementById('vao-viewer-img');
  const vaoViewerCounter = document.getElementById('vao-viewer-counter');
  const vaoViewerPrev = document.getElementById('vao-viewer-prev');
  const vaoViewerNext = document.getElementById('vao-viewer-next');

  // Stato viewer singolo
  let svImages = [], svIndex = 0, svTitle = '';
  let _svOpen = false;

  // ── Toggle Light / Dark mode ──────────────────────────────────────
  if (vaoThemeBtn) {
    vaoThemeBtn.addEventListener('click', e => {
      e.stopPropagation();
      const isDarkNow = overlay.classList.toggle('theme-dark');
      vaoThemeBtn.textContent = isDarkNow ? 'Light mode' : 'Dark mode';
      document.body.classList.toggle('vao-dark-mode', isDarkNow);
    });
  }

  // ── Apri overlay: griglia diretta stile Overview ──────────────────
  window.openViewAllOverlay = function(images, title, isDark) {
    if (!images || images.length === 0) return;
    if (!overlay) return;
    const COLS = 9;
    const dark = !!isDark;
    overlay.classList.toggle('theme-dark', dark);
    document.body.classList.toggle('vao-dark-mode', dark);
    if (vaoThemeBtn) vaoThemeBtn.textContent = dark ? 'Light mode' : 'Dark mode';
    vaoTitle.textContent = title;
    vaoGrid.innerHTML = '';
    vaoGrid.classList.remove('visible');
    vaoGrid.style.opacity = '';
    vaoGrid.style.pointerEvents = '';
    _closeViewer(true); // chiudi viewer senza resetCursor (overlay ancora aperto)

    // Costruisci celle griglia
    const maxBlanks = Math.max(1, Math.round(images.length / 36 * 3));
    const cells = [];
    let imgIdx = 0;
    let blanksInserted = 0;
    while (imgIdx < images.length) {
      const photosLeft    = images.length - imgIdx;
      const photosThisRow = Math.min(photosLeft, COLS);
      const blanksLeft    = maxBlanks - blanksInserted;
      const useBlank      = blanksLeft > 0 && photosThisRow >= 2 && Math.random() < 0.55;
      const blankCol      = useBlank ? (1 + Math.floor(Math.random() * (photosThisRow - 1))) : -1;
      for (let col = 0; col < photosThisRow + (useBlank ? 1 : 0); col++) {
        if (useBlank && col === blankCol) {
          cells.push({ type: 'blank' });
          blanksInserted++;
        } else {
          if (imgIdx < images.length) {
            cells.push({ type: 'img', img: images[imgIdx] });
            imgIdx++;
          }
        }
      }
    }

    const imgCells = cells.filter(c => c.type === 'img');
    cells.forEach((cell) => {
      if (cell.type === 'blank') {
        const blank = document.createElement('div');
        blank.className = 'vao-grid-blank';
        vaoGrid.appendChild(blank);
        return;
      }
      const img  = cell.img;
      const item = document.createElement('div');
      item.className = 'vao-grid-item';
      const im = document.createElement('img');
      im.src = img.url;
      im.loading = 'lazy';
      im.alt = title;
      im.addEventListener('load', function() {
        if (this.naturalWidth > this.naturalHeight) {
          const allItems   = Array.from(vaoGrid.querySelectorAll('.vao-grid-item, .vao-grid-blank'));
          const idx        = allItems.indexOf(item);
          const rowStart   = Math.floor(idx / 9) * 9;
          const rowEnd     = rowStart + 9;
          const rowItems   = allItems.slice(rowStart, rowEnd);
          const lscInRow   = rowItems.filter(el => el.classList.contains('is-landscape')).length;
          if (lscInRow < 3) item.classList.add('is-landscape');
        }
      });
      item.appendChild(im);
      item.addEventListener('mouseenter', () => { cursor.classList.add('hover'); });
      item.addEventListener('mouseleave', () => resetCursor());
      item.addEventListener('click', e => {
        e.stopPropagation();
        const imgI = imgCells.indexOf(cell);
        _openViewer(imgCells.map(c => c.img), imgI, title);
      });
      vaoGrid.appendChild(item);
    });

    overlay.classList.add('open');
    requestAnimationFrame(() => {
      vaoGrid.classList.add('visible');
      const items = vaoGrid.querySelectorAll('.vao-grid-item, .vao-grid-blank');
      items.forEach((item, i) => {
        const row   = Math.floor(i / COLS);
        const col   = i % COLS;
        const delay = (row + col) * 40;
        setTimeout(() => item.classList.add('appeared'), delay);
      });
    });
  };

  // ── Viewer singolo foto interno al VAO ────────────────────────────
  function _openViewer(images, idx, title) {
    svImages = images;
    svIndex  = idx;
    svTitle  = title;
    _svOpen  = true;
    _svRender();
    if (vaoViewer) vaoViewer.classList.remove('hidden');
    vaoGrid.style.opacity      = '0';
    vaoGrid.style.pointerEvents = 'none';
    cursorDot.style.visibility = '';
    _svUpdateCursor();
  }

  function _closeViewer(silent) {
    _svOpen  = false;
    svImages = [];
    if (vaoViewer) vaoViewer.classList.add('hidden');
    if (vaoGrid) {
      vaoGrid.style.opacity      = '';
      vaoGrid.style.pointerEvents = '';
    }
    if (!silent) {
      cursorDot.style.visibility = '';
      resetCursor();
    }
  }

  function _svRender() {
    if (!svImages.length) return;
    const img = svImages[svIndex];
    vaoViewerImg.classList.add('fade');
    setTimeout(() => {
      vaoViewerImg.src = img.url;
      vaoViewerImg.classList.remove('fade');
    }, 120);
    vaoViewerCounter.textContent =
      String(svIndex + 1).padStart(2, '0') + ' / ' + String(svImages.length).padStart(2, '0');
  }

  function _svNav(dir) {
    if (!svImages.length) return;
    svIndex = (svIndex + dir + svImages.length) % svImages.length;
    _svRender();
    _svUpdateCursor();
  }

  function _svUpdateCursor() {
    const img      = svImages[svIndex];
    const catLabel = (img && img.project && (img.project.category || img.project.title)) || svTitle || '';
    const numLabel = String(svIndex + 1).padStart(2,'0') + ' / ' + String(svImages.length).padStart(2,'0');
    setCursorHover(catLabel, numLabel);
  }

  // Frecce cliccabili
  if (vaoViewerPrev) vaoViewerPrev.addEventListener('click', e => { e.stopPropagation(); _svNav(-1); });
  if (vaoViewerNext) vaoViewerNext.addEventListener('click', e => { e.stopPropagation(); _svNav(1); });

  // Click sul viewer: metà sinistra = indietro, metà destra = avanti
  if (vaoViewer) {
    vaoViewer.addEventListener('click', e => {
      if (e.target.closest('.vao-viewer-nav')) return;
      if (!_svOpen) return;
      const dir = e.clientX >= window.innerWidth / 2 ? 1 : -1;
      _svNav(dir);
    });
  }

  // Tasti freccia per navigazione nel viewer
  document.addEventListener('keydown', e => {
    if (!overlay.classList.contains('open')) return;
    if (_svOpen) {
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown')  { e.preventDefault(); _svNav(1);  }
      if (e.key === 'ArrowLeft'  || e.key === 'ArrowUp')    { e.preventDefault(); _svNav(-1); }
      if (e.key === 'Escape')                                { _closeViewer(); }
    } else {
      if (e.key === 'Escape') window.closeViewAllOverlay();
    }
  });

  // ── Chiusura overlay ──────────────────────────────────────────────
  window.closeViewAllOverlay = function() {
    _closeViewer(true);
    overlay.classList.remove('open');
    document.body.classList.remove('vao-dark-mode');
    cursorDot.style.visibility = '';
    resetCursor();
  };

  vaoClose.addEventListener('click', window.closeViewAllOverlay);
  const vaoBackBtn = document.getElementById('vao-back');
  if (vaoBackBtn) vaoBackBtn.addEventListener('click', window.closeViewAllOverlay);
})();

"""

new_content = content[:start_idx] + new_block + content[end_idx:]

with open('static/site/index.html', 'w', encoding='utf-8') as f:
    f.write(new_content)

print('OK: blocco VAO sostituito con successo')
print(f'Nuova dimensione file: {len(new_content)} caratteri')
