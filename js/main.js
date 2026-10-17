/*
 * main.js — Orchestration : carte MapLibre (fond OSM France HOT),
 * clic -> altitude + viewshed, réglages (rayon, antenne, obstacles).
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
  let current = null;          // { lngLat, dem, zGround }
  let ctrl = null;             // AbortController du chargement en cours

  const el = {
    hint: document.getElementById("hint"),
    results: document.getElementById("results"),
    zGround: document.getElementById("z-ground"),
    resInfo: document.getElementById("res-info"),
    areaInfo: document.getElementById("area-info"),
    radius: document.getElementById("radius"),
    radiusNum: document.getElementById("radius-num"),
    radiusLabel: document.getElementById("radius-label"),
    obstacles: document.getElementById("obstacles"),
  };

  function getRadius() { return UI.radiusFromSlider(+el.radius.value); }
  function updateRadiusLabel() {
    const r = getRadius();
    el.radiusLabel.textContent = UI.fmtRadius(r);
    el.radiusNum.value = (r / 1000).toLocaleString("fr-FR", { maximumFractionDigits: 2 });
  }
  function setBusy(busy) { UI.showProgress(busy); }
  function abortCurrent() {
    if (ctrl) { ctrl.abort(); ctrl = null; }
  }
  function pickLayer() {
    return el.obstacles.checked ? WMS_DEM.LAYER_MNS : WMS_DEM.LAYER_MNT;
  }
  function mastElement() {
    const d = document.createElement("div");
    d.id = "mast-marker";
    return d;
  }

  async function onMapClick(e) {
    abortCurrent();
    ctrl = new AbortController();
    const signal = ctrl.signal;
    const lngLat = e.lngLat;
    const radius = getRadius();
    const lat = lngLat.lat * Math.PI / 180;
    const center3857 = maplibregl.MercatorCoordinate.fromLngLat(lngLat, 0);
    const half = radius / Math.cos(lat);   // mètres réels -> mètres Mercator

    setBusy(true);
    UI.setStatus("");
    RENDER.removeViewshed(map);

    try {
      // 1. altitude du sol au point cliqué (MNT)
      const zGround = await WMS_DEM.elevationAt(
        lngLat.lng, lngLat.lat, WMS_DEM.LAYER_MNT, signal
      );

      // 2. grille DEM autour du point (couche selon toggle obstacles)
      UI.setProgress(0, 2, "Chargement du terrain…");
      const dem = await WMS_DEM.fetchDem({
        cx: center3857.x, cy: center3857.y,
        half, layer: pickLayer(), signal,
      });
      dem.layer = pickLayer();

      // 3. viewshed : l'altitude du point cliqué est la hauteur d'observation
      UI.setProgress(1, 2, "Calcul de la visibilité…");
      const { visible, visCount } = VIEWSHED.compute(dem, center3857, zGround, radius);
      const mask = VIEWSHED.smooth(dem, visible, 1);

      // 4. rendu + marqueur
      RENDER.showViewshed(map, dem, mask);
      RENDER.showRadius(map, [lngLat.lng, lngLat.lat], radius);
      if (marker) marker.remove();
      marker = new maplibregl.Marker({ element: mastElement() })
        .setLngLat(lngLat)
        .addTo(map);

      // 5. panneau résultats
      const stepM = dem.step * Math.cos(lat);
      const area = visCount * stepM * stepM;
      el.zGround.textContent = UI.fmtAlt(zGround);
      el.resInfo.textContent = `${stepM.toFixed(stepM < 1 ? 1 : 0)} m (${dem.width}×${dem.height})`;
      el.areaInfo.textContent = UI.fmtArea(area);
      el.results.classList.remove("hidden");
      el.hint.classList.add("hidden");

      current = { lngLat, dem, zGround };
      ctrl = null;
      setBusy(false);
    } catch (err) {
      setBusy(false);
      if (err.name !== "AbortError") {
        UI.setStatus("Erreur : " + (err.message || err));
      }
    }
  }

  // Recalcul : réutilise la grille si elle couvre le rayon demandé
  // et si la couche n'a pas changé ; sinon re-télécharge.
  async function recompute() {
    if (!current) return;
    abortCurrent();
    ctrl = new AbortController();
    const signal = ctrl.signal;
    const radius = getRadius();
    const center3857 = maplibregl.MercatorCoordinate.fromLngLat(current.lngLat, 0);
    const lat = current.lngLat.lat * Math.PI / 180;
    const need = radius / Math.cos(lat);

    const [w, s, e, n] = current.dem.bbox;
    const covered = current.dem.layer === pickLayer() &&
      center3857.x - need >= w && center3857.x + need <= e &&
      center3857.y - need >= s && center3857.y + need <= n;

    setBusy(true);
    UI.setStatus("");
    try {
      let dem = current.dem;
      if (!covered) {
        dem = await WMS_DEM.fetchDem({
          cx: center3857.x, cy: center3857.y,
          half: need, layer: pickLayer(), signal,
        });
        dem.layer = pickLayer();
      }
      const { visible, visCount } = VIEWSHED.compute(dem, center3857, current.zGround, radius);
      const mask = VIEWSHED.smooth(dem, visible, 1);
      RENDER.showViewshed(map, dem, mask);
      RENDER.showRadius(map, [current.lngLat.lng, current.lngLat.lat], radius);

      const stepM = dem.step * Math.cos(lat);
      el.resInfo.textContent = `${stepM.toFixed(stepM < 1 ? 1 : 0)} m (${dem.width}×${dem.height})`;
      el.areaInfo.textContent = UI.fmtArea(visCount * stepM * stepM);
      current.dem = dem;
      setBusy(false);
    } catch (err) {
      setBusy(false);
      if (err.name !== "AbortError") UI.setStatus("Erreur : " + (err.message || err));
    }
  }

  map.on("load", () => {
    map.on("click", onMapClick);
  });

  el.radius.addEventListener("input", updateRadiusLabel);
  el.radius.addEventListener("change", () => { updateRadiusLabel(); recompute(); });
  el.radiusNum.addEventListener("change", () => {
    const km = parseFloat(el.radiusNum.value.replace(",", "."));
    if (Number.isFinite(km) && km > 0) {
      el.radius.value = UI.sliderFromRadius(Math.min(30000, Math.max(100, km * 1000)));
      updateRadiusLabel();
      recompute();
    }
  });
  el.obstacles.addEventListener("change", recompute);

  updateRadiusLabel();
})();
