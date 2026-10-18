/*
 * alti.js — Altitudes ponctuelles via l'API Altimétrie de la Géoplateforme
 * (https://data.geopf.fr/altimetrie/1.0/calcul/alti/rest/elevation.json).
 *
 * Ressource principale : ign_lidar_hd_mnx_mono_wld (LiDAR HD 50 cm,
 * MNT + MNS + MNH en une requête via measures=true).
 * Repli : ign_rge_alti_wld (RGE ALTI 1 m, MNT seul) si LiDAR HD
 * ne couvre pas le point (z = -99999).
 */
"use strict";

const ALTI = (() => {

  const URL_ELEVATION = "https://data.geopf.fr/altimetrie/1.0/calcul/alti/rest/elevation.json";
  const RES_LIDARHD = "ign_lidar_hd_mnx_mono_wld";
  const RES_RGE_ALTI = "ign_rge_alti_wld";
  const NO_DATA = -99999;

  function measureByTitle(elevation, prefix) {
    const m = (elevation.measures || []).find(m => String(m.title || "").startsWith(prefix));
    return m ? m.z : undefined;
  }

  async function fetchElevations(lon, lat, resource, signal) {
    const p = new URLSearchParams({
      lon: String(lon), lat: String(lat),
      resource,
      measures: "true", zonly: "false",
    });
    const res = await fetch(`${URL_ELEVATION}?${p.toString()}`, { signal });
    if (!res.ok) throw new Error(`Altimétrie HTTP ${res.status}`);
    const json = await res.json();
    if (!json.elevations || !json.elevations.length) {
      throw new Error("Réponse altimétrique vide");
    }
    return json.elevations[0];
  }

  /*
   * Altitudes d'un point : sol (MNT), surface (MNS) et hauteur d'obstacle (MNH).
   * Retourne { zGround, zSurface, zHeight } ; les valeurs non disponibles
   * sont null.
   */
  async function elevationAt(lon, lat, signal) {
    let e = await fetchElevations(lon, lat, RES_LIDARHD, signal);
    let zGround = e.z;
    let zSurface = measureByTitle(e, "IGN - LIDAR HD - MNS");
    let zHeight = measureByTitle(e, "IGN - LIDAR HD - MNH");

    if (zGround === NO_DATA) {
      // repli RGE ALTI : MNT seul, pas de MNS/MNH
      e = await fetchElevations(lon, lat, RES_RGE_ALTI, signal);
      zGround = e.z === NO_DATA ? null : e.z;
      zSurface = null;
      zHeight = null;
      if (zGround === null) throw new Error("Pas de donnée altimétrique ici (hors France ?)");
    }

    return {
      zGround: zGround === NO_DATA ? null : zGround,
      zSurface: zSurface === NO_DATA ? null : zSurface,
      zHeight: zHeight === NO_DATA ? null : zHeight,
    };
  }

  return {
    elevationAt,
  };
})();
