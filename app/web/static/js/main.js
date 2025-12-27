// app/web/static/js/main.js

document.addEventListener("DOMContentLoaded", () => {
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
    const muscleSelect = form ? form.querySelector("select[name='muscle_id']") : null;

    if (!input || !list || !endpoint || !muscleSelect) return;

    let timer = null;

    const renderList = (items, totalCount, query) => {
      list.innerHTML = "";
      const header = document.createElement("div");
      header.className = "mb-2 text-[11px] text-slate-400";
      if (query) {
        header.textContent = `${items.length} of ${totalCount} exercises`;
      } else {
        header.textContent = `${totalCount} exercises`;
      }
      list.appendChild(header);

      if (!items.length) {
        const empty = document.createElement("div");
        empty.className = "text-[11px] text-slate-500";
        empty.textContent = query ? "No matches yet." : "No exercises yet.";
        list.appendChild(empty);
        list.classList.remove("hidden");
        return;
      }
      items.forEach((item) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "block w-full text-left rounded-md border border-slate-800 bg-slate-900 px-3 py-2 text-xs text-slate-100 hover:bg-slate-800 transition-colors duration-150";
        const count = Number.isFinite(item.exercise_count)
          ? ` (${item.exercise_count})`
          : "";
        const row = document.createElement("div");
        row.className = "flex items-center justify-between gap-2";
        const left = document.createElement("div");
        left.className = "flex items-center gap-2";
        const name = document.createElement("span");
        name.textContent = `${item.name}${count}`;
        left.appendChild(name);
        if (item.muscle_name) {
          const muscle = document.createElement("span");
          muscle.className = "inline-flex items-center gap-1 text-[11px] text-slate-400";
          if (item.muscle_color) {
            const dot = document.createElement("span");
            dot.className = "inline-flex h-2 w-2 rounded-full";
            dot.style.backgroundColor = item.muscle_color;
            muscle.appendChild(dot);
          }
          const label = document.createElement("span");
          label.textContent = item.muscle_name;
          muscle.appendChild(label);
          left.appendChild(muscle);
        }
        row.appendChild(left);
        if (item.last_logged) {
          const date = document.createElement("span");
          date.className = "text-[10px] text-slate-400 whitespace-nowrap";
          date.textContent = item.last_logged;
          row.appendChild(date);
        }
        button.appendChild(row);
        button.addEventListener("click", () => {
          input.value = item.name;
          if (item.muscle_id && muscleSelect) {
            muscleSelect.value = String(item.muscle_id);
          }
          const weightInput = form ? form.querySelector("input[name='weight_used']") : null;
          const unitSelect = form ? form.querySelector("select[name='weight_unit']") : null;
          const setsInput = form ? form.querySelector("input[name='num_of_sets']") : null;
          if (weightInput && item.last_weight_used !== null && item.last_weight_used !== undefined) {
            weightInput.value = item.last_weight_used;
          }
          if (unitSelect && item.last_weight_unit) {
            unitSelect.value = item.last_weight_unit;
          }
          if (setsInput && item.last_num_of_sets !== null && item.last_num_of_sets !== undefined) {
            setsInput.value = item.last_num_of_sets;
          }
          list.classList.add("hidden");
        });
        list.appendChild(button);
      });
      list.classList.remove("hidden");
    };

    const fetchSuggestions = () => {
      const query = input.value.trim();
      const url = new URL(endpoint, window.location.origin);
      if (muscleSelect && muscleSelect.value) {
        url.searchParams.set("muscle_id", muscleSelect.value);
      }
      url.searchParams.set("q", query);

      fetch(url.toString(), { headers: { Accept: "application/json" } })
        .then((response) => response.json())
        .then((data) => {
          const items = data.items || [];
          if (!query) {
            list.classList.add("hidden");
            return;
          }
          renderList(items, data.count || 0, query);
        })
        .catch(() => {
          list.classList.add("hidden");
        });
    };

    if (muscleSelect) {
      muscleSelect.addEventListener("change", fetchSuggestions);
    }
    input.addEventListener("input", () => {
      if (timer) window.clearTimeout(timer);
      timer = window.setTimeout(fetchSuggestions, 200);
    });
    input.addEventListener("focus", fetchSuggestions);

    fetchSuggestions();
  });
});
