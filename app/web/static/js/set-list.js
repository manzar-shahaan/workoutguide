// app/web/static/js/set-list.js
//
// Dynamic per-set weight/reps rows on the add/edit exercise forms. Each
// set is its own row instead of one weight for the whole exercise ("75
// for 8, then 65 for 8 and 8" becomes three real rows, not an average).
// "Add set" clones the last row's weight -- the fast path is log one set,
// then tap Add and just adjust reps/weight down for drop sets.
// State lives in the #sets_json hidden input as a JSON array so the
// server doesn't have to parse repeated bracket-style form fields.

(() => {
  const wrapper = document.querySelector("[data-set-list]");
  if (!wrapper) return;

  const rowsContainer = document.getElementById("setRows");
  const hiddenInput = document.getElementById("sets_json");
  const addBtn = document.getElementById("addSetBtn");
  if (!rowsContainer || !hiddenInput || !addBtn) return;

  let sets = [];
  try {
    const parsed = JSON.parse(hiddenInput.value || "[]");
    if (Array.isArray(parsed) && parsed.length) sets = parsed;
  } catch (e) {
    sets = [];
  }
  if (!sets.length) sets = [{ weight_used: null, reps: null }];

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

      const weightInput = document.createElement("input");
      weightInput.type = "number";
      weightInput.step = "0.01";
      weightInput.placeholder = "Weight";
      weightInput.value = set.weight_used ?? "";
      weightInput.style.width = "auto";
      weightInput.className = "flex-1 min-w-0";
      weightInput.addEventListener("input", () => {
        const value = weightInput.value.trim();
        set.weight_used = value === "" ? null : parseFloat(value);
        serialize();
      });
      row.appendChild(weightInput);

      const xSpan = document.createElement("span");
      xSpan.className = "text-neutral-500 text-xs shrink-0";
      xSpan.textContent = "×";
      row.appendChild(xSpan);

      const repsInput = document.createElement("input");
      repsInput.type = "number";
      repsInput.placeholder = "Reps";
      repsInput.value = set.reps ?? "";
      repsInput.style.width = "auto";
      repsInput.className = "flex-1 min-w-0";
      repsInput.addEventListener("input", () => {
        const value = repsInput.value.trim();
        set.reps = value === "" ? null : parseInt(value, 10);
        serialize();
      });
      row.appendChild(repsInput);

      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.className = "shrink-0 text-neutral-500 hover:text-neutral-100 transition-colors duration-200 px-1";
      removeBtn.textContent = "✕";
      removeBtn.setAttribute("aria-label", "Remove set");
      removeBtn.addEventListener("click", () => {
        sets.splice(index, 1);
        if (!sets.length) sets.push({ weight_used: null, reps: null });
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
      weight_used: last ? last.weight_used : null,
      reps: last ? last.reps : null,
    });
    serialize();
    render();
  });

  // Exposed so a prefill (typeahead pick / muscle-map shortlist) can
  // replace the whole set list after this widget has already rendered.
  window.setExerciseSets = (newSets) => {
    if (!Array.isArray(newSets) || !newSets.length) return;
    sets = newSets.map((s) => ({
      weight_used: s.weight_used ?? null,
      reps: s.reps ?? null,
    }));
    serialize();
    render();
  };

  serialize();
  render();
})();
