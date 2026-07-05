// app/web/static/js/cardio-set-list.js
//
// Dynamic per-interval duration/distance rows for cardio exercises on the
// add/edit exercise forms -- steady-state is one row, HIIT/intervals/
// sprints can have several. Mirrors set-list.js's row-based UI, just
// duration+distance instead of weight+reps. Pace is derived and shown
// read-only, never stored, so it can't drift from the numbers typed in.

function parseDuration(raw) {
  const trimmed = (raw || "").trim();
  if (!trimmed) return null;
  const parts = trimmed.split(":").map((p) => p.trim());
  if (parts.some((p) => p === "" || Number.isNaN(Number(p)))) return null;
  const nums = parts.map(Number);
  if (nums.length === 1) return Math.round(nums[0] * 60); // bare number = minutes
  if (nums.length === 2) return nums[0] * 60 + nums[1]; // mm:ss
  if (nums.length === 3) return nums[0] * 3600 + nums[1] * 60 + nums[2]; // hh:mm:ss
  return null;
}

function formatDuration(totalSeconds) {
  if (totalSeconds === null || totalSeconds === undefined) return "";
  const s = Math.round(totalSeconds);
  const hh = Math.floor(s / 3600);
  const mm = Math.floor((s % 3600) / 60);
  const ss = s % 60;
  const pad = (n) => String(n).padStart(2, "0");
  return hh > 0 ? `${hh}:${pad(mm)}:${pad(ss)}` : `${mm}:${pad(ss)}`;
}

function formatPace(durationSeconds, distance, unit) {
  if (!durationSeconds || !distance) return "";
  return `${formatDuration(durationSeconds / distance)}/${unit}`;
}

(() => {
  const wrapper = document.querySelector("[data-cardio-set-list]");
  if (!wrapper) return;

  const rowsContainer = document.getElementById("cardioSetRows");
  const hiddenInput = document.getElementById("cardio_sets_json");
  const addBtn = document.getElementById("addCardioSetBtn");
  const distanceUnitSelect = document.querySelector("[data-distance-unit-select]");
  if (!rowsContainer || !hiddenInput || !addBtn) return;

  let sets = [];
  try {
    const parsed = JSON.parse(hiddenInput.value || "[]");
    if (Array.isArray(parsed) && parsed.length) sets = parsed;
  } catch (e) {
    sets = [];
  }
  if (!sets.length) sets = [{ duration_seconds: null, distance: null }];

  const unitLabel = () => (distanceUnitSelect ? distanceUnitSelect.value : "mi");

  const serialize = () => {
    hiddenInput.value = JSON.stringify(sets);
  };

  const render = () => {
    rowsContainer.innerHTML = "";
    sets.forEach((set, index) => {
      const row = document.createElement("div");
      row.className = "flex items-center gap-2";

      const setLabel = document.createElement("span");
      setLabel.className = "tabular text-xs text-neutral-500 w-5 shrink-0";
      setLabel.textContent = `${index + 1}.`;
      row.appendChild(setLabel);

      const durationInput = document.createElement("input");
      durationInput.type = "text";
      durationInput.inputMode = "numeric";
      durationInput.placeholder = "mm:ss";
      durationInput.value = set.duration_seconds != null ? formatDuration(set.duration_seconds) : "";
      durationInput.style.width = "auto";
      durationInput.className = "flex-1 min-w-0";
      row.appendChild(durationInput);

      const xSpan = document.createElement("span");
      xSpan.className = "text-neutral-500 text-xs shrink-0";
      xSpan.textContent = "·";
      row.appendChild(xSpan);

      const distanceInput = document.createElement("input");
      distanceInput.type = "number";
      distanceInput.step = "0.01";
      distanceInput.placeholder = `Distance (${unitLabel()})`;
      distanceInput.value = set.distance ?? "";
      distanceInput.style.width = "auto";
      distanceInput.className = "flex-1 min-w-0";
      row.appendChild(distanceInput);

      const paceEl = document.createElement("span");
      paceEl.className = "text-xs text-neutral-500 tabular shrink-0 w-16 text-right";
      paceEl.textContent = formatPace(set.duration_seconds, set.distance, unitLabel());
      row.appendChild(paceEl);

      durationInput.addEventListener("input", () => {
        set.duration_seconds = parseDuration(durationInput.value);
        serialize();
        paceEl.textContent = formatPace(set.duration_seconds, set.distance, unitLabel());
      });

      distanceInput.addEventListener("input", () => {
        const value = distanceInput.value.trim();
        set.distance = value === "" ? null : parseFloat(value);
        serialize();
        paceEl.textContent = formatPace(set.duration_seconds, set.distance, unitLabel());
      });

      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.className = "shrink-0 text-neutral-500 hover:text-neutral-100 transition-colors duration-200 px-1";
      removeBtn.textContent = "✕";
      removeBtn.setAttribute("aria-label", "Remove interval");
      removeBtn.addEventListener("click", () => {
        sets.splice(index, 1);
        if (!sets.length) sets.push({ duration_seconds: null, distance: null });
        serialize();
        render();
      });
      row.appendChild(removeBtn);

      rowsContainer.appendChild(row);
    });
  };

  addBtn.addEventListener("click", () => {
    const last = sets[sets.length - 1];
    sets.push({
      duration_seconds: last ? last.duration_seconds : null,
      distance: last ? last.distance : null,
    });
    serialize();
    render();
  });

  if (distanceUnitSelect) {
    // Re-render on unit change so each row's placeholder/pace suffix stays correct.
    distanceUnitSelect.addEventListener("change", render);
  }

  // Exposed so a prefill (typeahead pick / cardio quick-list) can replace
  // the whole interval list after this widget has already rendered.
  window.setCardioSets = (newSets, distanceUnit) => {
    if (!Array.isArray(newSets) || !newSets.length) return;
    sets = newSets.map((s) => ({
      duration_seconds: s.duration_seconds ?? null,
      distance: s.distance ?? null,
    }));
    if (distanceUnit && distanceUnitSelect) distanceUnitSelect.value = distanceUnit;
    serialize();
    render();
  };

  serialize();
  render();
})();
