/*
 * wmsDem.js — Téléchargement de grilles d'altitude (MNT/MNS) via le
 * WMS-Raster de la Géoplateforme (IGN) au format image/x-bil;bits=32
 * (float32 big-endian bruts, une valeur par pixel).
 *
 * Couches : ELEVATION.ELEVATIONGRIDCOVERAGE.HIGHRES     (MNT — terrain nu, 1 m)
 *           ELEVATION.ELEVATIONGRIDCOVERAGE.HIGHRES.MNS (MNS — avec obstacles)
 * CRS de travail : EPSG:3857 (Web Mercator, natif MapLibre).
 */
"use strict";

const WMS_DEM = (() => {

  const BASE = "https://data.geopf.fr/wms-r";
  const LAYER_MNT = "ELEVATION.ELEVATIONGRIDCOVERAGE.HIGHRES";
  const LAYER_MNS = "ELEVATION.ELEVATIONGRIDCOVERAGE.HIGHRES.MNS";
  const MAX_TILE = 4000;          // garde-fou < limite serveur 5010
  const MAX_CELLS = 16e6;         // plafond mémoire ~64 Mo float32

  // Cache LRU : clé = layer|centre|demi-largeur
  const cache = new Map();
  const CACHE_MAX = 6;
  function cacheGet(key) {
    if (!cache.has(key)) return undefined;
    const v = cache.get(key);
    cache.delete(key); cache.set(key, v);   // refresh LRU
    return v;
  }
  function cachePut(key, value) {
    if (cache.has(key)) cache.delete(key);
    cache.set(key, value);
    if (cache.size > CACHE_MAX) cache.delete(cache.keys().next().value);
  }

  function buildUrl(layer, bbox, width, height, crs = "EPSG:3857") {
    const p = new URLSearchParams({
      SERVICE: "WMS", VERSION: "1.3.0", REQUEST: "GetMap",
      LAYERS: layer, STYLES: "normal",
      FORMAT: "image/x-bil;bits=32",
      CRS: crs,
      BBOX: bbox.join(","),
      WIDTH: String(width), HEIGHT: String(height),
    });
    return `${BASE}?${p.toString()}`;
  }

  // Décode un payload BIL en Float32Array (big-endian).
  // En WMS 1.3.0 la première ligne du flux correspond au bord sud
  // de la bbox. On retourne le tableau pour que row 0 = nord.
  function decodeBil(buffer, width, height) {
    const src = new DataView(buffer);
    const out = new Float32Array(width * height);
    for (let i = 0; i < width * height; i++) {
      out[i] = src.getFloat32(i * 4, false); // big-endian
    }
    const flipped = new Float32Array(width * height);
    for (let r = 0; r < height; r++) {
      const srcRow = height - 1 - r;
      flipped.set(out.subarray(srcRow * width, (srcRow + 1) * width), r * width);
    }
    return flipped;
  }

  async function fetchTile(layer, bbox, width, height, signal, crs = "EPSG:3857") {
    const res = await fetch(buildUrl(layer, bbox, width, height, crs), { signal });
    if (!res.ok) throw new Error(`WMS HTTP ${res.status}`);
    const buf = await res.arrayBuffer();
    if (buf.byteLength < width * height * 4) {
      const txt = new TextDecoder().decode(buf.slice(0, 500));
      throw new Error(`Réponse WMS inattendue : ${txt.slice(0, 200)}`);
    }
    return decodeBil(buf, width, height);
  }

  /*
   * Grille d'altitude centrée sur (cx, cy) [EPSG:3857], demi-largeur
   * `half` en mètres. Retourne :
   * { grid: Float32Array, width, height, bbox: [w,s,e,n], step }
   * avec row 0 = nord, col 0 = ouest.
   */
  async function fetchDem({ cx, cy, half, layer, signal, onProgress }) {
    let size = Math.min(MAX_TILE, Math.ceil(2 * half));
    size = Math.min(size, Math.floor(Math.sqrt(MAX_CELLS)));
    const step = (2 * half) / size;

    // bbox arrondie sur le pas, avec 2 cellules de marge
    const w0 = Math.floor((cx - half) / step) * step;
    const s0 = Math.floor((cy - half) / step) * step;
    const width = size + 2, height = size + 2;
    const bbox = [w0, s0, w0 + width * step, s0 + height * step];

    const key = `${layer}|${cx.toFixed(1)}|${cy.toFixed(1)}|${half.toFixed(1)}`;
    const hit = cacheGet(key);
    if (hit) return hit;

    if (onProgress) onProgress(0, 1);
    const grid = await fetchTile(layer, bbox, width, height, signal);
    if (onProgress) onProgress(1, 1);

    const result = { grid, width, height, bbox, step };
    cachePut(key, result);
    return result;
  }

  return {
    LAYER_MNT, LAYER_MNS,
    fetchDem,
    // Altitude ponctuelle via une requête BIL 1x1.
    // CRS:84 = WGS84 axes (lon, lat) — l'ordre d'axe de EPSG:4326
    // en WMS 1.3.0 est (lat, lon), d'où CRS:84 pour éviter l'inversion.
    async elevationAt(lon, lat, layer = LAYER_MNT, signal) {
      const res = await fetch(
        buildUrl(layer, [lon, lat, lon + 1e-7, lat + 1e-7], 1, 1, "CRS:84"),
        { signal }
      );
      if (!res.ok) throw new Error(`WMS HTTP ${res.status}`);
      const buf = await res.arrayBuffer();
      if (buf.byteLength < 4) throw new Error("Pas de donnée altimétrique ici (hors France ?)");
      return new DataView(buf).getFloat32(0, false);
    },
  };
})();
