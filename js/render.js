/*
 * render.js — Rendu du masque de visibilité en canvas, injecté dans
 * MapLibre comme image raster géoréférencée (EPSG:3857).
 * Le canvas est 1 pixel = 1 cellule de la grille DEM.
 */
"use strict";

const RENDER = (() => {

  const LAYER_ID = "viewshed-layer";
  const SOURCE_ID = "viewshed-source";
  const CIRCLE_SOURCE = "radius-circle-source";
  const CIRCLE_LAYER = "radius-circle-layer";

  // Masque -> canvas RGBA (vert translucide pour visible)
  function maskToCanvas(dem, mask, color = [26, 150, 80, 200]) {
    const { width, height } = dem;
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    const img = ctx.createImageData(width, height);
    for (let i = 0; i < width * height; i++) {
      const o = i * 4;
      if (mask[i]) {
        img.data[o] = color[0];
        img.data[o + 1] = color[1];
        img.data[o + 2] = color[2];
        img.data[o + 3] = color[3];
      } else {
        img.data[o + 3] = 0;
      }
    }
    ctx.putImageData(img, 0, 0);
    return canvas;
  }

  function showViewshed(map, dem, mask) {
    removeViewshed(map);
    const canvas = maskToCanvas(dem, mask);
    const url = canvas.toDataURL();

    map.addSource(SOURCE_ID, {
      type: "image",
      url,
      coordinates: [
        [dem.bbox[0], dem.bbox[3]], // nord-ouest
        [dem.bbox[2], dem.bbox[3]], // nord-est
        [dem.bbox[2], dem.bbox[1]], // sud-est
        [dem.bbox[0], dem.bbox[1]], // sud-ouest
      ],
    });
    map.addLayer({
      id: LAYER_ID,
      type: "raster",
      source: SOURCE_ID,
      paint: { "raster-opacity": 0.85, "raster-fade-duration": 0 },
    }, insertBefore(map));
  }

  function removeViewshed(map) {
    if (map.getLayer(LAYER_ID)) map.removeLayer(LAYER_ID);
    if (map.getSource(SOURCE_ID)) map.removeSource(SOURCE_ID);
  }

  // Cercle matérialisant le rayon de calcul (polygon en WGS84, sans turf)
  function showRadius(map, lngLat, radiusMeters) {
    removeRadius(map);
    const [lng, lat] = lngLat;
    const latR = radiusMeters / 111320;
    const lngR = radiusMeters / (111320 * Math.max(Math.cos(lat * Math.PI / 180), 0.01));
    const coords = [];
    for (let a = 0; a <= 360; a += 3) {
      const t = a * Math.PI / 180;
      coords.push([lng + lngR * Math.cos(t), lat + latR * Math.sin(t)]);
    }
    map.addSource(CIRCLE_SOURCE, {
      type: "geojson",
      data: { type: "Feature", geometry: { type: "Polygon", coordinates: [coords] } },
    });
    map.addLayer({
      id: CIRCLE_LAYER,
      type: "line",
      source: CIRCLE_SOURCE,
      paint: { "line-color": "#666", "line-width": 1, "line-dasharray": [3, 3] },
    }, insertBefore(map));
  }

  function removeRadius(map) {
    if (map.getLayer(CIRCLE_LAYER)) map.removeLayer(CIRCLE_LAYER);
    if (map.getSource(CIRCLE_SOURCE)) map.removeSource(CIRCLE_SOURCE);
  }

  // insérer au-dessus du fond HOT mais sous le reste
  function insertBefore(map) {
    const layers = map.getStyle().layers;
    const idx = layers.findIndex(l => l.id === "hot");
    if (idx >= 0 && idx + 1 < layers.length) return layers[idx + 1].id;
    return undefined;
  }

  return {
    showViewshed, removeViewshed,
    showRadius, removeRadius,
  };
})();
