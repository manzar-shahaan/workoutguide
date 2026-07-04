// app/web/static/js/region-picker.js
//
// Small inline tap-to-select body figure used on the manual "add/edit
// exercise" forms, so a typed-in exercise can still be tagged with body
// regions (same exercise_catalog_region data the muscle-map home page
// writes) instead of only ever getting tags via the map flow. No cap on
// how many regions -- tap order sets priority (1st tapped = primary
// target, 2nd = secondary, and so on), shown in the hint text.

import { createBodyMap } from "./body-map-render.js";

document.addEventListener("DOMContentLoaded", () => {
  const container = document.querySelector("[data-region-picker]");
  if (!container) return;

  const mapEl = container.querySelector("[data-region-picker-map]");
  const hint = container.querySelector("[data-region-picker-hint]");
  const hiddenInput = document.getElementById("region_slugs");
  const toggleButtons = container.querySelectorAll("[data-view-toggle]");
  if (!mapEl || !hint || !hiddenInput) return;

  let selected = hiddenInput.value ? hiddenInput.value.split(",").filter(Boolean) : [];

  const highlighter = createBodyMap({
    container: mapEl,
    view: "anterior",
    bodyColor: "#f5f5f5", // near-white
    highlightColor: "#22c55e",
    style: { width: "100%", maxWidth: "140px", margin: "0 auto" },
    onClick: ({ muscle }) => toggleRegion(muscle),
  });

  const sync = () => {
    highlighter.setSelected(selected);
    hiddenInput.value = selected.join(",");
    hint.textContent = selected.length
      ? selected.map((s, i) => `${i + 1}. ${s.replace(/-/g, " ")}`).join(", ")
      : "Optional: tap to tag muscles, in priority order";
  };

  const toggleRegion = (slug) => {
    const index = selected.indexOf(slug);
    if (index !== -1) {
      selected.splice(index, 1);
    } else {
      selected.push(slug);
    }
    sync();
  };

  toggleButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const nextView = btn.dataset.viewToggle === "posterior" ? "posterior" : "anterior";
      toggleButtons.forEach((b) => b.classList.toggle("is-active", b === btn));
      highlighter.setView(nextView);
      sync(); // setView rebuilds polygons, so re-apply current selection
    });
  });

  sync();
});
