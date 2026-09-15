// main.js — SmartQA Demo Store
// Phase 1: Minimal JavaScript. Most logic lives in Flask/Python.
// This file exists as a placeholder and for any small UX helpers.

// Auto-dismiss flash messages after 4 seconds
document.addEventListener("DOMContentLoaded", function () {
  setTimeout(function () {
    document.querySelectorAll(".alert").forEach(function (el) {
      el.style.transition = "opacity 0.5s";
      el.style.opacity = "0";
      setTimeout(function () { el.remove(); }, 500);
    });
  }, 4000);
});
