/*
 * wmsDem.js — Altitude ponctuelle (MNT/MNS) via le WMS-Raster de la
 * Géoplateforme (IGN) au format image/x-bil;bits=32 (float32 little-endian).
 *
 * Couches : ELEVATION.ELEVATIONGRIDCOVERAGE.HIGHRES     (MNT — terrain nu)
 *           ELEVATION.ELEVATIONGRIDCOVERAGE.HIGHRES.MNS (MNS — avec obstacles)
 */
"use strict";

const WMS_DEM = (() => {

  const BASE = "https://data.geopf.fr/wms-r";
  const LAYER_MNT = "ELEVATION.ELEVATIONGRIDCOVERAGE.HIGHRES";
  const LAYER_MNS = "ELEVATION.ELEVATIONGRIDCOVERAGE.HIGHRES.MNS";

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

  // Altitude ponctuelle via une requête BIL 1x1.
  // CRS:84 = WGS84 axes (lon, lat) — l'ordre d'axe de EPSG:4326
  // en WMS 1.3.0 est (lat, lon), d'où CRS:84 pour éviter l'inversion.
  async function elevationAt(lon, lat, layer = LAYER_MNT, signal) {
    const url = buildUrl(layer, [lon, lat, lon + 1e-7, lat + 1e-7], 1, 1, "CRS:84");
    const res = await fetch(url, { signal });
    if (!res.ok) throw new Error(`WMS HTTP ${res.status}`);
    const buf = await res.arrayBuffer();
    if (buf.byteLength < 4) throw new Error("Pas de donnée altimétrique ici (hors France ?)");
    return new DataView(buf).getFloat32(0, true);
  }

  return {
    LAYER_MNT, LAYER_MNS,
    elevationAt,
  };
})();
