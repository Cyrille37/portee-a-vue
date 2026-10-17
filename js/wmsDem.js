/*
 * wmsDem.js — Téléchargement de grilles d'altitude (MNT/MNS) via le
 * WMS-Raster de la Géoplateforme (IGN) au format image/x-bil;bits=32
 * (float32 little-endian bruts, une valeur par pixel).
 *
 * Couches : ELEVATION.ELEVATIONGRIDCOVERAGE.HIGHRES     (MNT — terrain nu, 1 m)
 *           ELEVATION.ELEVATIONGRIDCOVERAGE.HIGHRES.MNS (MNS — avec obstacles)
 * CRS de travail : EPSG:3857 (Web Mercator, natif MapLibre).
 *
 * Cache : les réponses WMS sont mises en Cache API (persistantes entre
 * les sessions) via leur URL déterministe, plus un LRU mémoire au-dessus.
 */
"use strict";

const WMS_DEM = (() => {

  const BASE = "https://data.geopf.fr/wms-r";
  const LAYER_MNT = "ELEVATION.ELEVATIONGRIDCOVERAGE.HIGHRES";
  const LAYER_MNS = "ELEVATION.ELEVATIONGRIDCOVERAGE.HIGHRES.MNS";
  const MAX_TILE = 4000;          // garde-fou < limite serveur 5010
  const MAX_CELLS = 16e6;          // plafond mémoire ~64 Mo float32
  const CACHE_NAME = "portee-a-vue-wms-dem-v1";

  // LRU mémoire : clé = URL WMS (déterministe)
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

  // ---- Cache API (persistant) --------------------------------------
  let httpCache = null;
  async function httpCacheOpen() {
    if (!("caches" in window)) return null;
    if (!httpCache) {
      try { httpCache = await caches.open(CACHE_NAME); }
      catch { return null; }
    }
    return httpCache;
  }
  async function httpCacheGet(url) {
    const c = await httpCacheOpen();
    if (!c) return null;
    try {
      const res = await c.match(url);
      return res ? await res.arrayBuffer() : null;
    } catch { return null; }
  }
  async function httpCachePut(url, buffer) {
    const c = await httpCacheOpen();
    if (!c) return;
    try { await c.put(url, new Response(buffer.slice(0))); } catch {}
  }

  async function clearCache() {
    cache.clear();
    httpCache = null;
    if ("caches" in window) {
      try { await caches.delete(CACHE_NAME); } catch {}
    }
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

  // Décode un payload BIL en Float32Array (little-endian).
  // En WMS 1.3.0 la première ligne du flux correspond au bord sud
  // de la bbox. On retourne le tableau pour que row 0 = nord.
  function decodeBil(buffer, width, height) {
    const src = new DataView(buffer);
    const out = new Float32Array(width * height);
    for (let i = 0; i < width * height; i++) {
      out[i] = src.getFloat32(i * 4, true); // little-endian
    }
    const flipped = new Float32Array(width * height);
    for (let r = 0; r < height; r++) {
      const srcRow = height - 1 - r;
      flipped.set(out.subarray(srcRow * width, (srcRow + 1) * width), r * width);
    }
    return flipped;
  }

  async function fetchTile(url, width, height, signal) {
    let buf = await httpCacheGet(url);
    if (!buf) {
      const res = await fetch(url, { signal });
      if (!res.ok) throw new Error(`WMS HTTP ${res.status}`);
      buf = await res.arrayBuffer();
      if (buf.byteLength < width * height * 4) {
        const txt = new TextDecoder().decode(buf.slice(0, 500));
        throw new Error(`Réponse WMS inattendue : ${txt.slice(0, 200)}`);
      }
      await httpCachePut(url, buf);
    }
    if (buf.byteLength < width * height * 4) {
      throw new Error("Réponse WMS en cache incomplète");
    }
    return decodeBil(buf, width, height);
  }

  /*
   * Grille d'altitude centrée sur (cx, cy) [EPSG:3857], demi-largeur
   * `half` en mètres. Retourne :
   * { grid: Float32Array, width, height, bbox: [w,s,e,n], step }
   * avec row 0 = nord, col 0 = ouest.
   *
   * La bbox est ancrée sur une grille quantifiée de maille `half` et
   * couvre toujours 3x3 mailles : tous les clics situés dans une même
   * maille produisent exactement la même URL → hit cache sans requête
   * réseau. La maille de 3x3 garantit la couverture du rayon complet
   * quelle que soit la position du clic dans sa maille.
   */
  async function fetchDem({ cx, cy, half, layer, signal, onProgress }) {
    const w = Math.floor((cx - half) / half) * half;
    const s = Math.floor((cy - half) / half) * half;
    const span = 3 * half;
    const bbox = [w, s, w + span, s + span];

    let size = Math.min(MAX_TILE, Math.ceil(span));
    size = Math.min(size, Math.floor(Math.sqrt(MAX_CELLS)));
    const width = size, height = size;
    const step = span / size;

    const url = buildUrl(layer, bbox, width, height);
    const hit = cacheGet(url);
    if (hit) {
      console.debug("WMS cache mémoire :", url);
      return hit;
    }

    if (onProgress) onProgress(0, 1);
    const grid = await fetchTile(url, width, height, signal);
    if (onProgress) onProgress(1, 1);

    const result = { grid, width, height, bbox, step };
    cachePut(url, result);
    return result;
  }

  // Altitude ponctuelle via une requête BIL 1x1.
  // CRS:84 = WGS84 axes (lon, lat) — l'ordre d'axe de EPSG:4326
  // en WMS 1.3.0 est (lat, lon), d'où CRS:84 pour éviter l'inversion.
  // Coordonnées quantifiées à ~1 m (1e-5°) pour mutualiser le cache.
  async function elevationAt(lon, lat, layer = LAYER_MNT, signal) {
    const lonQ = Math.round(lon * 1e5) / 1e5;
    const latQ = Math.round(lat * 1e5) / 1e5;
    const url = buildUrl(layer, [lonQ, latQ, lonQ + 1e-7, latQ + 1e-7], 1, 1, "CRS:84");
    let buf = await httpCacheGet(url);
    if (buf) console.debug("WMS cache HTTP :", url);
    if (!buf) {
      const res = await fetch(url, { signal });
      if (!res.ok) throw new Error(`WMS HTTP ${res.status}`);
      buf = await res.arrayBuffer();
      if (buf.byteLength < 4) throw new Error("Pas de donnée altimétrique ici (hors France ?)");
      await httpCachePut(url, buf);
    }
    return new DataView(buf).getFloat32(0, true);
  }

  return {
    LAYER_MNT, LAYER_MNS,
    fetchDem, elevationAt, clearCache,
  };
})();
