/*
 * main.js — Orchestration : carte MapLibre (fond OSM France HOT),
 * clic -> altitude du point (MNT sol, MNS surface, hauteur d'obstacle).
 */
"use strict";

(() => {

  function readViewFromHash() {
    const m = /^#(\d+(?:\.\d+)?)\/(-?\d+(?:\.\d+)?)\/(-?\d+(?:\.\d+)?)/.exec(location.hash);
    if (!m) return null;
    const zoom = Math.min(20, Math.max(0, parseFloat(m[1])));
    const lng = parseFloat(m[2]);
    const lat = parseFloat(m[3]);
    if (!Number.isFinite(zoom) || Math.abs(lng) > 180 || Math.abs(lat) > 90) return null;
    return { center: [lng, lat], zoom };
  }

  function writeViewToHash() {
    const { lng, lat } = map.getCenter();
    const z = map.getZoom().toFixed(2);
    const hash = `#${z}/${lat.toFixed(6)}/${lng.toFixed(6)}`;
    if (hash !== location.hash) {
      history.replaceState(null, "", hash);
    }
  }

  const view = readViewFromHash();
  const map = new maplibregl.Map({
    container: "map",
    style: {
      version: 8,
      sources: {
        hot: {
          type: "raster",
          tiles: [
            "https://a.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png",
            "https://b.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png",
            "https://c.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png",
          ],
          tileSize: 256,
          attribution: "© OpenStreetMap France, Humanitarian OSM Team",
        },
      },
      layers: [{ id: "hot", type: "raster", source: "hot" }],
    },
    center: view ? view.center : [0.683059, 47.422219],
    zoom: view ? view.zoom : 12,
  });

  map.on("moveend", writeViewToHash);
  window.addEventListener("hashchange", () => {
    const v = readViewFromHash();
    if (v) map.jumpTo(v);
  });
  writeViewToHash();

  map.addControl(new maplibregl.NavigationControl());

  let marker = null;
  let ctrl = null;             // AbortController du chargement en cours

  const el = {
    hint: document.getElementById("hint"),
    results: document.getElementById("results"),
    clickCoords: document.getElementById("click-coords"),
    zHeight: document.getElementById("z-height"),
    zGround: document.getElementById("z-ground"),
    zSurface: document.getElementById("z-surface"),
  };

  function setBusy(busy) { UI.showProgress(busy); }
  function isBusy() { return ctrl !== null; }
  function abortCurrent() {
    if (ctrl) { ctrl.abort(); ctrl = null; }
  }
  function clickMarkerElement() {
    const d = document.createElement("div");
    d.id = "click-marker";
    return d;
  }

  async function onMapClick(e) {
    if (isBusy()) return;
    abortCurrent();
    ctrl = new AbortController();
    const signal = ctrl.signal;
    const lngLat = e.lngLat;

    setBusy(true);
    UI.setStatus("");

    try {
      // altitudes au point cliqué : sol (MNT) et surface (MNS)
      UI.setBusyLabel("Recherche de l'altitude…");
      const [zGround, zSurface] = await Promise.all([
        WMS_DEM.elevationAt(lngLat.lng, lngLat.lat, WMS_DEM.LAYER_MNT, signal),
        WMS_DEM.elevationAt(lngLat.lng, lngLat.lat, WMS_DEM.LAYER_MNS, signal),
      ]);

      // marqueur
      if (marker) marker.remove();
      marker = new maplibregl.Marker({ element: clickMarkerElement() })
        .setLngLat(lngLat)
        .addTo(map);

      // panneau résultats
      el.clickCoords.textContent = `${lngLat.lat.toFixed(6)}/${lngLat.lng.toFixed(6)}`;
      el.zGround.textContent = UI.fmtAlt(zGround);
      el.zSurface.textContent = UI.fmtAlt(zSurface);
      el.zHeight.textContent = UI.fmtAlt(zSurface - zGround);
      el.results.classList.remove("hidden");
      el.hint.classList.add("hidden");

      ctrl = null;
      setBusy(false);
    } catch (err) {
      setBusy(false);
      if (err.name !== "AbortError") {
        UI.setStatus("Erreur : " + (err.message || err));
      }
    }
  }

  map.on("load", () => {
    map.on("click", onMapClick);
  });

})();
