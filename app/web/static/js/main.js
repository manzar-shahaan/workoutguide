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
    const count = block.querySelector("[data-exercise-count]");
    const endpoint = block.dataset.suggestionsEndpoint;
    const form = block.closest("form");
    const muscleSelect = form ? form.querySelector("select[name='muscle_id']") : null;

    if (!input || !list || !count || !endpoint || !muscleSelect) return;

    let timer = null;

    const renderList = (items) => {
      list.innerHTML = "";
      if (!items.length) {
        list.classList.add("hidden");
        return;
      }
      items.forEach((item) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "block w-full text-left rounded-md border border-slate-800 bg-slate-900 px-3 py-2 text-xs text-slate-100 hover:bg-slate-800 transition-colors duration-150";
        button.textContent = item.name;
        button.addEventListener("click", () => {
          input.value = item.name;
          list.classList.add("hidden");
        });
        list.appendChild(button);
      });
      list.classList.remove("hidden");
    };

    const fetchSuggestions = () => {
      const muscleId = muscleSelect.value;
      if (!muscleId) {
        count.textContent = "0";
        list.classList.add("hidden");
        return;
      }

      const query = input.value.trim();
      const url = new URL(endpoint, window.location.origin);
      url.searchParams.set("muscle_id", muscleId);
      if (query) {
        url.searchParams.set("q", query);
      }

      fetch(url.toString(), { headers: { Accept: "application/json" } })
        .then((response) => response.json())
        .then((data) => {
          count.textContent = `${data.count}`;
          if (query) {
            renderList(data.items || []);
          } else {
            list.classList.add("hidden");
          }
        })
        .catch(() => {
          list.classList.add("hidden");
        });
    };

    muscleSelect.addEventListener("change", fetchSuggestions);
    input.addEventListener("input", () => {
      if (timer) window.clearTimeout(timer);
      timer = window.setTimeout(fetchSuggestions, 200);
    });

    fetchSuggestions();
  });
});
