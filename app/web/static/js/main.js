// app/web/static/js/main.js

// Applies a suggestion/shortlist item's fields onto the exercise form.
// Shared by the typeahead suggestion list, the muscle-map shortlist, and
// the home page's cardio quick-list (home.js) so all three paths prefill
// identically. Branches on item.modality: cardio hands off duration/
// distance intervals + distance unit instead of weight/reps + regions.
function applyExercisePrefill(form, item) {
  if (!form || !item) return;
  const nameInput = form.querySelector("input[name='exercise_name']");
  const unitSelect = form.querySelector("select[name='weight_unit']");
  const regionSlugsInput = form.querySelector("input[name='region_slugs']");

  if (nameInput && item.name) nameInput.value = item.name;

  if (item.modality && window.setExerciseModality) {
    window.setExerciseModality(item.modality, item.cardio_target);
  }

  if (item.modality === "cardio") {
    if (Array.isArray(item.last_sets) && item.last_sets.length && window.setCardioSets) {
      window.setCardioSets(item.last_sets, item.last_distance_unit);
    }
    return;
  }

  if (unitSelect && item.last_weight_unit) unitSelect.value = item.last_weight_unit;
  if (regionSlugsInput && item.region_slugs) {
    regionSlugsInput.value = item.region_slugs.join(",");
  }
  if (Array.isArray(item.last_sets) && item.last_sets.length && window.setExerciseSets) {
    window.setExerciseSets(item.last_sets);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  // Muscle-map / cardio-quick-list handoff: home.js sends the tapped
  // item's fields via query params instead of an in-page click, since the
  // map/quick-list lives on a different page than the form.
  const newExerciseForm = document.querySelector("[data-exercise-suggestions]")?.closest("form");
  if (newExerciseForm) {
    const params = new URLSearchParams(window.location.search);
    if (params.has("exercise_name") || params.has("modality")) {
      const modality = params.get("modality");
      let lastSets = null;
      const setsParam = modality === "cardio" ? "cardio_sets_json" : "sets_json";
      if (params.has(setsParam)) {
        try {
          lastSets = JSON.parse(params.get(setsParam));
        } catch (e) {
          lastSets = null;
        }
      }
      applyExercisePrefill(newExerciseForm, {
        name: params.get("exercise_name"),
        modality: modality,
        cardio_target: params.get("cardio_target"),
        last_weight_unit: params.get("weight_unit"),
        last_distance_unit: params.get("distance_unit"),
        last_sets: lastSets,
        region_slugs: params.get("region_slugs") ? params.get("region_slugs").split(",") : null,
      });
    }
  }

  const menuButton = document.getElementById("userMenuButton");
  const overlay = document.getElementById("userMenuOverlay");

  if (!menuButton || !overlay) return;

  const dismissSelectors = "[data-user-menu-dismiss]";
  const dismissElements = overlay.querySelectorAll(dismissSelectors);

  const openMenu = () => {
    overlay.classList.remove("hidden");
    overlay.setAttribute("aria-hidden", "false");
  };

  const closeMenu = () => {
    overlay.classList.add("hidden");
    overlay.setAttribute("aria-hidden", "true");
  };

  menuButton.addEventListener("click", () => {
    const isHidden = overlay.classList.contains("hidden");
    if (isHidden) {
      openMenu();
    } else {
      closeMenu();
    }
  });

  dismissElements.forEach((el) => {
    el.addEventListener("click", () => {
      closeMenu();
    });
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeMenu();
    }
  });

  const suggestionBlocks = document.querySelectorAll("[data-exercise-suggestions]");
  suggestionBlocks.forEach((block) => {
    const input = block.querySelector("[data-exercise-input]");
    const list = block.querySelector("[data-exercise-list]");
    const endpoint = block.dataset.suggestionsEndpoint;
    const form = block.closest("form");

    if (!input || !list || !endpoint) return;

    let timer = null;

    const renderList = (items, totalCount, query) => {
      list.innerHTML = "";
      const header = document.createElement("div");
      header.className = "mb-2 text-[11px] text-neutral-400";
      if (query) {
        header.textContent = `${items.length} of ${totalCount} exercises`;
      } else {
        header.textContent = `${totalCount} exercises`;
      }
      list.appendChild(header);

      if (!items.length) {
        const empty = document.createElement("div");
        empty.className = "text-[11px] text-neutral-500";
        empty.textContent = query ? "No matches yet." : "No exercises yet.";
        list.appendChild(empty);
        list.classList.remove("hidden");
        return;
      }
      items.forEach((item) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "block w-full text-left rounded-md border border-neutral-800 bg-neutral-900 px-3 py-2 text-xs text-neutral-100 hover:bg-neutral-800 transition-colors duration-150";
        const count = Number.isFinite(item.exercise_count)
          ? ` (${item.exercise_count})`
          : "";
        const row = document.createElement("div");
        row.className = "flex items-center justify-between gap-2";
        const name = document.createElement("span");
        name.textContent = `${item.name}${count}`;
        row.appendChild(name);
        if (item.last_logged) {
          const date = document.createElement("span");
          date.className = "text-[10px] text-neutral-400 whitespace-nowrap";
          date.textContent = item.last_logged;
          row.appendChild(date);
        }
        button.appendChild(row);
        button.addEventListener("click", () => {
          applyExercisePrefill(form, item);
          list.classList.add("hidden");
        });
        list.appendChild(button);
      });
      list.classList.remove("hidden");
    };

    const fetchSuggestions = () => {
      const query = input.value.trim();
      const url = new URL(endpoint, window.location.origin);
      url.searchParams.set("q", query);

      fetch(url.toString(), { headers: { Accept: "application/json" } })
        .then((response) => response.json())
        .then((data) => {
          const items = data.items || [];
          renderList(items, data.count || 0, query);
        })
        .catch(() => {
          list.classList.add("hidden");
        });
    };

    input.addEventListener("input", () => {
      if (timer) window.clearTimeout(timer);
      timer = window.setTimeout(fetchSuggestions, 200);
    });
    input.addEventListener("focus", () => {
      fetchSuggestions();
    });

    document.addEventListener("click", (event) => {
      if (!block.contains(event.target)) {
        list.classList.add("hidden");
      }
    });
  });
});
