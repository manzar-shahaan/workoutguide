// app/web/static/js/region-picker.js
//
// Small inline tap-to-select body figure used on the manual "add/edit
// exercise" forms, so a typed-in exercise can still be tagged with up to
// 2 body regions (same exercise_catalog_region data the muscle-map home
// page writes) instead of only ever getting tags via the map flow.

import createBodyHighlighter, { ModelType } from "https://cdn.jsdelivr.net/npm/body-highlighter@3.0.2/dist/body-highlighter.esm.js";

document.addEventListener("DOMContentLoaded", () => {
  const container = document.querySelector("[data-region-picker]");
  if (!container) return;

  const mapEl = container.querySelector("[data-region-picker-map]");
  const hint = container.querySelector("[data-region-picker-hint]");
  const hiddenInput = document.getElementById("region_slugs");
  const toggleButtons = container.querySelectorAll("[data-view-toggle]");
  if (!mapEl || !hint || !hiddenInput) return;

  const MAX_SELECTED = 2;
  let selected = hiddenInput.value ? hiddenInput.value.split(",").filter(Boolean) : [];
  let currentView = ModelType.ANTERIOR;

  const highlighter = createBodyHighlighter({
    container: mapEl,
    type: currentView,
    bodyColor: "#404040", // neutral-700
    highlightedColors: ["#22c55e"],
    style: { width: "100%", maxWidth: "140px", margin: "0 auto" },
    onClick: ({ muscle }) => toggleRegion(muscle),
  });

  const sync = () => {
    highlighter.update({
      data: selected.map((slug) => ({ name: slug, muscles: [slug], frequency: 1 })),
    });
    hiddenInput.value = selected.join(",");
    hint.textContent = selected.length
      ? selected.map((s) => s.replace(/-/g, " ")).join(" + ")
      : "Optional: tap to tag muscles";
  };

  const toggleRegion = (slug) => {
    const index = selected.indexOf(slug);
    if (index !== -1) {
      selected.splice(index, 1);
    } else {
      selected.push(slug);
      if (selected.length > MAX_SELECTED) selected.shift();
    }
    sync();
  };

  toggleButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      currentView = btn.dataset.viewToggle === "posterior" ? ModelType.POSTERIOR : ModelType.ANTERIOR;
      toggleButtons.forEach((b) => b.classList.toggle("is-active", b === btn));
      highlighter.update({ type: currentView });
    });
  });

  sync();
});
