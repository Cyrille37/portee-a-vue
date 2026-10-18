/*
 * lidarCoverage.js — Couverture LiDAR HD (dalles 1 km diffusées) via le WFS
 * de la Géoplateforme (TYPENAMES=IGNF_LIDAR-HD_METADONNEE:metadata).
 *
 * Chargement par bbox du viewport (ordre WFS 2.0 / EPSG:4326 : lat,lon),
 * avec LRU mémoire par tuile ~0.5° et plafond de features par requête.
 */
"use strict";

const LIDAR_COVERAGE = (() => {

  const WFS_URL = "https://data.geopf.fr/wfs";
  const TYPENAMES = "IGNF_LIDAR-HD_METADONNEE:metadata";
  const TILE = 0.5;             // tuile de cache en degrés
  const MAX_COUNT = 5000;        // plafond features par requête WFS
  const LRU_MAX = 64;            // tuiles en mémoire
  const MIN_ZOOM = 9;            // pas de chargement sous ce zoom

  const tileCache = new Map();   // clé "x,y" -> FeatureCollection GeoJSON
  const pending = new Map();     // clé tuile -> Promise

  function tileKey(lon, lat) {
    return `${Math.floor(lon / TILE)},${Math.floor(lat / TILE)}`;
  }

  function tilesForBBox(w, s, e, n) {
    const keys = new Set();
    for (let x = Math.floor(w / TILE); x <= Math.floor(e / TILE); x++) {
      for (let y = Math.floor(s / TILE); y <= Math.floor(n / TILE); y++) {
        keys.add(`${x},${y}`);
      }
    }
    return [...keys];
  }

  function bboxOfTile(key) {
    const [x, y] = key.split(",").map(Number);
    return { w: x * TILE, s: y * TILE, e: (x + 1) * TILE, n: (y + 1) * TILE };
  }

  async function fetchTile(key, signal) {
    const { w, s, e, n } = bboxOfTile(key);
    // WFS 2.0, SRSNAME=EPSG:4326 : ordre d'axe (lat, lon)
    const bbox = `${s},${w},${n},${e}`;
    const p = new URLSearchParams({
      SERVICE: "WFS", VERSION: "2.0.0", REQUEST: "GetFeature",
      TYPENAMES, OUTPUTFORMAT: "application/json",
      COUNT: String(MAX_COUNT),
      SRSNAME: "EPSG:4326", BBOX: bbox,
    });
    const res = await fetch(`${WFS_URL}?${p.toString()}`, { signal });
    if (!res.ok) throw new Error(`WFS HTTP ${res.status}`);
    const json = await res.json();
    const features = json.features || [];
    if (features.length >= MAX_COUNT) {
      console.warn("Couverture LiDAR HD : plafond de features atteint sur la tuile", key);
    }
    return { type: "FeatureCollection", features };
  }

  function cachePut(key, value) {
    if (tileCache.has(key)) tileCache.delete(key);
    tileCache.set(key, value);
    if (tileCache.size > LRU_MAX) tileCache.delete(tileCache.keys().next().value);
  }

  /*
   * Charge les tuiles couvrant la bbox (w,s,e,n en degrés lon/lat).
   * Retourne la liste des clés de tuiles réellement chargées (nouvelles).
   */
  async function loadBBox(w, s, e, n, { signal } = {}) {
    const keys = tilesForBBox(w, s, e, n);
    const toLoad = keys.filter(k => !tileCache.has(k));
    await Promise.all(toLoad.map(async k => {
      let p = pending.get(k);
      if (!p) {
        p = fetchTile(k, signal).then(fc => { cachePut(k, fc); return fc; })
          .finally(() => pending.delete(k));
        pending.set(k, p);
      }
      return p;
    }));
    return toLoad;
  }

  function has(w, s, e, n) {
    return tilesForBBox(w, s, e, n).every(k => tileCache.has(k));
  }

  // Test d'appartenance point-in-polygon (MultiPolygon/Polygon, anneaux)
  function pointInRing(lon, lat, ring) {
    let inside = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const xi = ring[i][0], yi = ring[i][1];
      const xj = ring[j][0], yj = ring[j][1];
      if (((yi > lat) !== (yj > lat)) &&
          (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi)) inside = !inside;
    }
    return inside;
  }

  function pointInPolygon(lon, lat, coords) {
    if (!pointInRing(lon, lat, coords[0])) return false;
    for (let h = 1; h < coords.length; h++) {
      if (pointInRing(lon, lat, coords[h])) return false; // trou
    }
    return true;
  }

  /*
   * Le point est-il dans une dalle diffusée connue (et chargée) ?
   * Retourne true/false, ou null si la zone n'est pas encore chargée.
   */
  function coversPoint(lon, lat) {
    const key = tileKey(lon, lat);
    const fc = tileCache.get(key);
    if (!fc) return null;
    for (const f of fc.features) {
      const g = f.geometry;
      if (!g) continue;
      const polys = g.type === "MultiPolygon" ? g.coordinates : [g.coordinates];
      for (const poly of polys) {
        if (pointInPolygon(lon, lat, poly)) return true;
      }
    }
    return false;
  }

  function getCachedFeatures() {
    const features = [];
    for (const fc of tileCache.values()) features.push(...fc.features);
    return { type: "FeatureCollection", features };
  }

  return {
    MIN_ZOOM,
    loadBBox, has, coversPoint, getCachedFeatures,
  };
})();
