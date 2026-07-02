// app/web/static/js/home.js
//
// Muscle-map exercise picker on the home/workouts page. Tapping a region
// fetches a shortlist (your exercises first, unlogged wger suggestions
// below, de-emphasized); tapping an item hands off to /exercises/new via
// query params, where main.js's applyExercisePrefill picks it back up.

import createBodyHighlighter, { ModelType } from "https://cdn.jsdelivr.net/npm/body-highlighter@3.0.2/dist/body-highlighter.esm.js";

document.addEventListener("DOMContentLoaded", () => {
  const mapContainer = document.getElementById("bodyMap");
  if (!mapContainer) return; // not on the home page

  const drawerOverlay = document.getElementById("regionDrawerOverlay");
  const drawerTitle = document.getElementById("drawerTitle");
  const drawerBody = document.getElementById("drawerBody");
  const clearBtn = document.getElementById("mapClearBtn");
  const mapHint = document.getElementById("mapHint");
  const newExerciseUrl = mapContainer.dataset.newExerciseUrl;
  const shortlistEndpoint = mapContainer.dataset.shortlistEndpoint;
  const viewToggleButtons = document.querySelectorAll("[data-view-toggle]");

  const MAX_SELECTED = 2;
  let selectedRegions = []; // slugs, order = tap order (first = primary)
  let currentView = ModelType.ANTERIOR;

  const highlighter = createBodyHighlighter({
    container: mapContainer,
    type: currentView,
    bodyColor: "#404040", // neutral-700: visible silhouette against black, no color signal
    highlightedColors: ["#22c55e"], // the one accent color, only on what's selected
    style: { width: "100%", maxWidth: "280px", margin: "0 auto" },
    onClick: ({ muscle }) => toggleRegion(muscle),
  });

  const syncHighlight = () => {
    highlighter.update({
      data: selectedRegions.map((slug) => ({ name: slug, muscles: [slug], frequency: 1 })),
    });
  };

  const closeDrawer = () => {
    drawerOverlay.classList.add("hidden");
    drawerOverlay.setAttribute("aria-hidden", "true");
  };

  const openDrawer = () => {
    drawerOverlay.classList.remove("hidden");
    drawerOverlay.setAttribute("aria-hidden", "false");
  };

  const regionLabel = (slug) => slug.replace(/-/g, " ");

  const buildCard = ({ name, subtitle, imageUrl, dimmed, onSelect }) => {
    const button = document.createElement("button");
    button.type = "button";
    const borderClass = dimmed ? "border-dashed border-neutral-800" : "border-neutral-800";
    const opacityClass = dimmed ? "opacity-60 hover:opacity-90" : "hover:border-neutral-600";
    button.className = `flex w-full items-center gap-3 rounded-lg border ${borderClass} bg-neutral-900 p-3 text-left transition-opacity duration-150 ${opacityClass}`;

    const thumb = document.createElement("div");
    thumb.className = "h-12 w-12 flex-shrink-0 overflow-hidden rounded bg-neutral-800";
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
    subEl.className = "truncate text-xs text-neutral-500";
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
    if (item.muscle_id) url.searchParams.set("muscle_id", item.muscle_id);
    if (item.last_weight_used !== undefined && item.last_weight_used !== null) {
      url.searchParams.set("weight_used", item.last_weight_used);
    }
    if (item.last_weight_unit) url.searchParams.set("weight_unit", item.last_weight_unit);
    if (item.last_num_of_sets !== undefined && item.last_num_of_sets !== null) {
      url.searchParams.set("num_of_sets", item.last_num_of_sets);
    }
    if (selectedRegions.length) url.searchParams.set("region_slugs", selectedRegions.join(","));
    window.location.href = url.toString();
  };

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
      card.classList.add("mb-2");
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
        card.classList.add("mb-2");
        drawerBody.appendChild(card);
      });
    }
  };

  const fetchShortlist = () => {
    if (!selectedRegions.length) {
      closeDrawer();
      return;
    }
    const url = new URL(shortlistEndpoint, window.location.origin);
    url.searchParams.set("regions", selectedRegions.join(","));
    drawerTitle.textContent = selectedRegions.map(regionLabel).join(" + ");
    drawerBody.innerHTML = '<p class="text-sm text-neutral-500">Loading…</p>';
    openDrawer();

    fetch(url.toString(), { headers: { Accept: "application/json" } })
      .then((response) => response.json())
      .then((data) => renderDrawer(data))
      .catch(() => {
        drawerBody.innerHTML = '<p class="text-sm text-neutral-500">Couldn\'t load exercises.</p>';
      });
  };

  const toggleRegion = (slug) => {
    const index = selectedRegions.indexOf(slug);
    if (index !== -1) {
      selectedRegions.splice(index, 1);
    } else {
      selectedRegions.push(slug);
      if (selectedRegions.length > MAX_SELECTED) selectedRegions.shift();
    }
    syncHighlight();
    clearBtn.classList.toggle("hidden", selectedRegions.length === 0);
    mapHint.textContent = selectedRegions.length
      ? `Selected: ${selectedRegions.map(regionLabel).join(" + ")}`
      : "Tap a muscle to see exercises";
    fetchShortlist();
  };

  clearBtn.addEventListener("click", () => {
    selectedRegions = [];
    syncHighlight();
    clearBtn.classList.add("hidden");
    mapHint.textContent = "Tap a muscle to see exercises";
    closeDrawer();
  });

  drawerOverlay.querySelectorAll("[data-drawer-dismiss]").forEach((el) => {
    el.addEventListener("click", closeDrawer);
  });

  viewToggleButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      currentView = btn.dataset.viewToggle === "posterior" ? ModelType.POSTERIOR : ModelType.ANTERIOR;
      viewToggleButtons.forEach((b) => b.classList.toggle("is-active", b === btn));
      highlighter.update({ type: currentView });
    });
  });
});
