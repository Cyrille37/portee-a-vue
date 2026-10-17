/*
 * viewshed.js — Calcul de la surface de vue directe (line of sight)
 * sur une grille d'altitude, par balayage radial autour de l'antenne.
 *
 * Pour chaque azimut, on suit le rayon du centre vers l'extérieur en
 * maintenant la pente maximale apparente depuis le sommet de l'antenne.
 * Une cellule est visible si sa pente apparente est >= à la pente max
 * courante ; sinon masquée. Puis lissage léger du masque.
 */
"use strict";

const VIEWSHED = (() => {

  /*
   * dem      : { grid, width, height, bbox, step } — grid[row*w+col], row 0 = nord
   * center   : { x, y } en EPSG:3857 (position de l'antenne)
   * antennaZ : altitude absolue du sommet de l'antenne
   * radius   : rayon en mètres (distance réelle au sol)
   */
  function compute(dem, center, antennaZ, radius) {
    const { grid, width, height, bbox, step } = dem;
    const [w0, s0, e0, n0] = bbox;

    // position de l'antenne dans la grille (indices flottants)
    const cx = (center.x - w0) / step;
    const cy = (n0 - center.y) / step; // row 0 = nord

    // facteur Mercator : 1 mètre réel = `merc` mètres projetés
    const lat = 2 * Math.atan(Math.exp(center.y / 6378137)) - Math.PI / 2;
    const merc = 1 / Math.cos(lat);
    const rCells = (radius * merc) / step;
    const maxR = Math.ceil(rCells);

    // densité angulaire : l'espacement entre rayons au bord du disque
    // ne doit pas dépasser la taille d'une cellule, sinon trous dans le masque
    const nAng = Math.min(20000, Math.max(360, Math.ceil(2 * Math.PI * rCells)));
    const dA = (2 * Math.PI) / nAng;
    const visible = new Uint8Array(width * height);
    let visCount = 0;

    for (let a = 0; a < nAng; a++) {
      const dx = Math.cos(a * dA), dy = Math.sin(a * dA);
      let maxSlope = -Infinity;

      for (let r = 1; r <= maxR; r++) {
        const col = Math.round(cx + dx * r);
        const row = Math.round(cy - dy * r);
        if (col < 0 || col >= width || row < 0 || row >= height) break;

        const z = grid[row * width + col];
        if (!Number.isFinite(z)) continue;

        const d = Math.max(r * step / merc, 0.5); // distance réelle
        const slope = (z - antennaZ) / d;
        if (slope >= maxSlope) {
          if (!visible[row * width + col]) {
            visible[row * width + col] = 1;
            visCount++;
          }
          if (slope > maxSlope) maxSlope = slope;
        }
      }
    }
    return { visible, visCount };
  }

  // Lissage : cellule masquée avec majorité de voisines visibles -> visible.
  function smooth(dem, mask, iterations = 1) {
    const { width, height } = dem;
    let src = mask;
    for (let it = 0; it < iterations; it++) {
      const out = new Uint8Array(src.length);
      for (let r = 1; r < height - 1; r++) {
        for (let c = 1; c < width - 1; c++) {
          const i = r * width + c;
          let n = 0;
          for (let dr = -1; dr <= 1; dr++)
            for (let dc = -1; dc <= 1; dc++)
              n += src[(r + dr) * width + (c + dc)];
          out[i] = n >= 5 ? 1 : src[i];
        }
      }
      src = out;
    }
    return src;
  }

  return { compute, smooth };
})();
