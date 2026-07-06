// app/web/static/js/home.js
//
// Muscle-map exercise picker on the home/workouts page. Tapping a region
// fetches a shortlist (your exercises first, unlogged wger suggestions
// below, de-emphasized); tapping an item hands off to /exercises/new via
// query params, where main.js's applyExercisePrefill picks it back up.

import { createBodyMap } from "./body-map-render.js";

document.addEventListener("DOMContentLoaded", () => {
  const mapContainer = document.getElementById("bodyMap");
  if (!mapContainer) return; // not on the home page

  const shortlistPanel = document.getElementById("shortlistPanel");
  const drawerTitle = document.getElementById("drawerTitle");
  const drawerBody = document.getElementById("drawerBody");
  const clearBtn = document.getElementById("mapClearBtn");
  const mapHint = document.getElementById("mapHint");
  const mapCard = document.getElementById("mapCard");
  const newExerciseUrl = mapContainer.dataset.newExerciseUrl;
  const shortlistEndpoint = mapContainer.dataset.shortlistEndpoint;
  const viewToggleButtons = document.querySelectorAll("[data-view-toggle]");
  const overdueRegions = (mapContainer.dataset.overdueRegions || "").split(",").filter(Boolean);

  const modeToggleButtons = document.querySelectorAll("[data-mode-toggle]");

  let selectedRegions = []; // slugs, order = tap order (first = primary), no cap

  const highlighter = createBodyMap({
    container: mapContainer,
    view: "anterior",
    bodyColor: "#f5f5f5", // near-white: flat fill, thin dark stroke does the definition
    highlightColor: "#22c55e", // the one accent color, only on what's selected
    pulsingSlugs: overdueRegions, // "needs training soon" -- white/grey/black cycle, see base.html
    style: { width: "100%", maxWidth: "280px", margin: "0 auto" },
    onClick: ({ muscle }) => toggleRegion(muscle),
  });

  const syncHighlight = () => {
    highlighter.setSelected(selectedRegions);
  };

  const closePanel = () => {
    shortlistPanel.classList.add("hidden");
  };

  const openPanel = () => {
    shortlistPanel.classList.remove("hidden");
  };

  const regionLabel = (slug) => slug.replace(/-/g, " ");

  const buildCard = ({ name, subtitle, imageUrl, dimmed, onSelect }) => {
    const button = document.createElement("button");
    button.type = "button";
    const surfaceClass = dimmed ? "border border-dashed border-white/10" : "surface-raised";
    const opacityClass = dimmed ? "opacity-60 hover:opacity-90" : "";
    button.className = `flex w-full items-center gap-3 rounded-2xl ${surfaceClass} p-3 text-left transition-opacity duration-150 ${opacityClass}`;

    const thumb = document.createElement("div");
    thumb.className = "h-12 w-12 flex-shrink-0 overflow-hidden rounded-xl bg-neutral-800";
    if (imageUrl) {
      const img = document.createElement("img");
      img.src = imageUrl;
      img.alt = "";
      img.className = "h-full w-full object-cover";
      img.loading = "lazy";
      img.onerror = () => thumb.remove();
      thumb.appendChild(img);
    }
    button.appendChild(thumb);

    const text = document.createElement("div");
    text.className = "min-w-0 flex-1";
    const nameEl = document.createElement("p");
    nameEl.className = "truncate text-sm text-neutral-100 capitalize";
    nameEl.textContent = name;
    const subEl = document.createElement("p");
    subEl.className = "truncate text-xs text-neutral-500 tabular";
    subEl.textContent = subtitle;
    text.appendChild(nameEl);
    text.appendChild(subEl);
    button.appendChild(text);

    button.addEventListener("click", onSelect);
    return button;
  };

  const goToForm = (item) => {
    const url = new URL(newExerciseUrl, window.location.origin);
    if (item.name) url.searchParams.set("exercise_name", item.name);
    if (item.last_weight_unit) url.searchParams.set("weight_unit", item.last_weight_unit);
    if (Array.isArray(item.last_sets) && item.last_sets.length) {
      url.searchParams.set("sets_json", JSON.stringify(item.last_sets));
    }
    if (selectedRegions.length) url.searchParams.set("region_slugs", selectedRegions.join(","));
    window.location.href = url.toString();
  };

  // Cardio has no muscle regions to tap, so the cardio side of the
  // strength/cardio toggle is just a shortcut straight to the add-exercise
  // form set up for a timed activity: endurance metric + a Cardio tag
  // pre-selected (main.js reads these off the URL and switches the form).
  // Strength stays on the map -- the default.
  modeToggleButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.dataset.modeToggle !== "cardio") return;
      const url = new URL(newExerciseUrl, window.location.origin);
      url.searchParams.set("metric_type", "endurance");
      url.searchParams.set("tags", "cardio");
      window.location.href = url.toString();
    });
  });

  const renderDrawer = (data) => {
    drawerTitle.textContent = selectedRegions.map(regionLabel).join(" + ");
    drawerBody.innerHTML = "";

    const yourExercises = data.your_exercises || [];
    const suggestions = data.suggestions || [];

    if (!yourExercises.length && !suggestions.length) {
      const empty = document.createElement("p");
      empty.className = "text-sm text-neutral-500";
      empty.textContent = "Nothing here yet.";
      drawerBody.appendChild(empty);
      return;
    }

    yourExercises.forEach((item) => {
      const parts = [];
      if (item.last_weight_used) parts.push(`${item.last_weight_used} ${item.last_weight_unit || ""}`.trim());
      if (item.last_num_of_sets) parts.push(`${item.last_num_of_sets} sets`);
      if (item.last_logged) parts.push(`last ${item.last_logged}`);
      const card = buildCard({
        name: item.name,
        subtitle: parts.join(" · ") || "Logged before",
        imageUrl: item.image_url,
        dimmed: false,
        onSelect: () => goToForm(item),
      });
      drawerBody.appendChild(card);
    });

    if (suggestions.length) {
      const divider = document.createElement("p");
      divider.className = "mt-3 mb-2 text-[11px] uppercase tracking-wide text-neutral-600";
      divider.textContent = "Not logged yet";
      drawerBody.appendChild(divider);

      suggestions.forEach((item) => {
        const card = buildCard({
          name: item.name,
          subtitle: "Not logged yet",
          imageUrl: item.image_url,
          dimmed: true,
          onSelect: () => goToForm(item),
        });
          drawerBody.appendChild(card);
      });
    }
  };

  const fetchShortlist = () => {
    if (!selectedRegions.length) {
      closePanel();
      return;
    }
    const url = new URL(shortlistEndpoint, window.location.origin);
    url.searchParams.set("regions", selectedRegions.join(","));
    drawerTitle.textContent = selectedRegions.map(regionLabel).join(" + ");
    drawerBody.innerHTML = '<p class="text-sm text-neutral-500">Loading…</p>';
    openPanel();

    fetch(url.toString(), { headers: { Accept: "application/json" } })
      .then((response) => response.json())
      .then((data) => renderDrawer(data))
      .catch(() => {
        drawerBody.innerHTML = '<p class="text-sm text-neutral-500">Couldn\'t load exercises.</p>';
      });
  };

  const toggleRegion = (slug) => {
    const index = selectedRegions.indexOf(slug);
    let added = false;
    if (index !== -1) {
      selectedRegions.splice(index, 1);
    } else {
      selectedRegions.push(slug);
      added = true;
    }
    syncHighlight();
    clearBtn.classList.toggle("hidden", selectedRegions.length === 0);
    mapHint.textContent = selectedRegions.length
      ? `Selected: ${selectedRegions.map(regionLabel).join(" + ")}`
      : "Tap a muscle to see exercises";
    if (added && mapCard) {
      mapCard.classList.remove("is-pulsing");
      // eslint-disable-next-line no-unused-expressions
      mapCard.offsetWidth; // restart the CSS animation
      mapCard.classList.add("is-pulsing");
    }
    fetchShortlist();
  };

  clearBtn.addEventListener("click", () => {
    selectedRegions = [];
    syncHighlight();
    clearBtn.classList.add("hidden");
    mapHint.textContent = "Tap a muscle to see exercises";
    closePanel();
  });

  viewToggleButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const nextView = btn.dataset.viewToggle === "posterior" ? "posterior" : "anterior";
      viewToggleButtons.forEach((b) => b.classList.toggle("is-active", b === btn));
      highlighter.setView(nextView);
      syncHighlight(); // setView rebuilds polygons, so re-apply current selection
    });
  });
});
