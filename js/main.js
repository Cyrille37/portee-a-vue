/*
 * main.js — Orchestration : carte MapLibre (fond OSM France HOT),
 * couverture LiDAR HD (tuiles vectorielles TMS Géoplateforme),
 * clic -> altitude du point (MNT sol, MNS surface, MNH hauteur d'obstacle)
 * via l'API Altimétrie de la Géoplateforme.
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
    coverageCheck: document.getElementById("coverage-check"),
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

  // ---- Couverture LiDAR HD (TMS vectoriel) --------------------------

  const COVERAGE_SOURCE = "lidar-coverage-source";
  const COVERAGE_FILL = "lidar-coverage-fill";
  const COVERAGE_LINE = "lidar-coverage-line";
  let coverageVisible = el.coverageCheck.checked;

  function addCoverageLayers() {
    map.addSource(COVERAGE_SOURCE, {
      type: "vector",
      // schéma XYZ standard (ordonnée haut-gauche), vérifié sur tuiles réelles
      tiles: ["https://data.geopf.fr/tms/1.0.0/IGNF_LIDAR-HD_METADONNEE/{z}/{x}/{y}.pbf"],
      minzoom: 6,
      maxzoom: 14,
      attribution: "Couverture LiDAR HD © IGN Géoplateforme",
    });
    map.addLayer({
      id: COVERAGE_FILL,
      type: "fill",
      source: COVERAGE_SOURCE,
      "source-layer": "metadata",
      paint: { "fill-color": "#1a73e8", "fill-opacity": 0.15 },
    });
    map.addLayer({
      id: COVERAGE_LINE,
      type: "line",
      source: COVERAGE_SOURCE,
      "source-layer": "metadata",
      paint: { "line-color": "#1a73e8", "line-width": 0.5, "line-opacity": 0.5 },
    });
  }

  function setCoverageVisible(visible) {
    coverageVisible = visible;
    for (const id of [COVERAGE_FILL, COVERAGE_LINE]) {
      if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
    }
  }

  // ---- Clic -> altitudes --------------------------------------------

  async function onMapClick(e) {
    if (isBusy()) return;
    abortCurrent();
    ctrl = new AbortController();
    const signal = ctrl.signal;
    const lngLat = e.lngLat;

    setBusy(true);
    UI.setStatus("");

    try {
      // altitudes au point cliqué : sol (MNT), surface (MNS), hauteur (MNH)
      UI.setBusyLabel("Recherche de l'altitude…");
      const { zGround, zSurface, zHeight } = await ALTI.elevationAt(lngLat.lng, lngLat.lat, signal);

      // marqueur
      if (marker) marker.remove();
      marker = new maplibregl.Marker({ element: clickMarkerElement() })
        .setLngLat(lngLat)
        .addTo(map);

      // panneau résultats
      el.clickCoords.textContent = `${lngLat.lat.toFixed(6)}/${lngLat.lng.toFixed(6)}`;
      el.zGround.textContent = UI.fmtAlt(zGround);
      el.zSurface.textContent = UI.fmtAlt(zSurface);
      if (zHeight === null) {
        el.zHeight.textContent = "n.d. (hors LiDAR HD)";
      } else {
        el.zHeight.textContent = UI.fmtAlt(zHeight);
      }
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
    addCoverageLayers();
    setCoverageVisible(coverageVisible);
    map.on("click", onMapClick);
  });

  el.coverageCheck.addEventListener("change", () => {
    setCoverageVisible(el.coverageCheck.checked);
  });

})();
