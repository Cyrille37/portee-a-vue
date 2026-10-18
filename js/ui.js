/*
 * ui.js — Helpers UI : formats, progression, statut.
 */
"use strict";

const UI = (() => {

  function fmtAlt(z) {
    return Number.isFinite(z) ? z.toLocaleString("fr-FR", { maximumFractionDigits: 1 }) + " m" : "—";
  }

  const busyOverlay = document.getElementById("busy-overlay");
  const busyLabel = document.getElementById("busy-label");

  function showProgress(show) {
    busyOverlay.classList.toggle("hidden", !show);
    if (show) setBusyLabel("Chargement…");
  }
  function setBusyLabel(label) {
    busyLabel.textContent = label;
  }
  function setStatus(msg) {
    document.getElementById("status").textContent = msg || "";
  }

  return {
    fmtAlt,
    showProgress, setBusyLabel, setStatus,
  };
})();
