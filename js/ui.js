/*
 * ui.js — Helpers UI : slider logarithmique rayon, formats, progression, statut.
 */
"use strict";

const UI = (() => {

  const R_MIN = 100, R_MAX = 30000; // mètres

  function radiusFromSlider(v) { // v : 0..1000
    const t = v / 1000;
    const r = R_MIN * Math.pow(R_MAX / R_MIN, t);
    // arrondi à 2 chiffres significatifs pour des valeurs lisibles
    const mag = Math.pow(10, Math.floor(Math.log10(r)) - 1);
    return Math.max(R_MIN, Math.round(r / mag) * mag);
  }
  function sliderFromRadius(r) {
    const t = Math.log(r / R_MIN) / Math.log(R_MAX / R_MIN);
    return Math.round(t * 1000);
  }
  function fmtRadius(m) {
    return m >= 1000
      ? (m / 1000).toLocaleString("fr-FR", { maximumFractionDigits: m % 1000 === 0 ? 0 : 1 }) + " km"
      : m + " m";
  }
  function fmtAlt(z) {
    return Number.isFinite(z) ? z.toLocaleString("fr-FR", { maximumFractionDigits: 1 }) + " m" : "—";
  }
  function fmtArea(m2) {
    return m2 >= 1e6
      ? (m2 / 1e6).toLocaleString("fr-FR", { maximumFractionDigits: 1 }) + " km²"
      : Math.round(m2).toLocaleString("fr-FR") + " m²";
  }

  function showProgress(show) {
    document.getElementById("progress").classList.toggle("hidden", !show);
    if (show) setProgress(0, 1, "Chargement du terrain…");
  }
  function setProgress(done, total, label) {
    document.getElementById("progress-fill").style.width = (100 * done / Math.max(total, 1)) + "%";
    document.getElementById("progress-label").textContent = label;
  }
  function setStatus(msg) {
    document.getElementById("status").textContent = msg || "";
  }

  return {
    R_MIN, R_MAX,
    radiusFromSlider, sliderFromRadius,
    fmtRadius, fmtAlt, fmtArea,
    showProgress, setProgress, setStatus,
  };
})();
