// app/web/static/js/tag-picker.js
//
// Multi-select tag chips on the add/edit exercise forms. Tags are the
// descriptive "what is this" axis (Cardio, Agility, Plyometrics, ...) --
// an activity can carry several at once, independent of how it's logged
// (metric_type) or which muscles it hits (regions). Selection lives in the
// #tags hidden input as a comma-separated slug list, mirroring #region_slugs.
//
// Runs immediately (script sits after the markup) so window.setExerciseTags
// exists before main.js's prefill runs.
(() => {
  const picker = document.querySelector("[data-tag-picker]");
  if (!picker) return;

  const hiddenInput = document.getElementById("tags");
  const chips = picker.querySelectorAll("[data-tag-chip]");
  if (!hiddenInput || !chips.length) return;

  let selected = new Set(
    (hiddenInput.value || "").split(",").map((s) => s.trim()).filter(Boolean)
  );

  const sync = () => {
    // Preserve chip (vocabulary) order rather than click order -- tags are
    // unordered, so a stable display order reads cleaner.
    const ordered = [];
    chips.forEach((chip) => {
      const slug = chip.dataset.tagChip;
      const on = selected.has(slug);
      chip.classList.toggle("is-active", on);
      chip.setAttribute("aria-pressed", on ? "true" : "false");
      if (on) ordered.push(slug);
    });
    hiddenInput.value = ordered.join(",");
  };

  chips.forEach((chip) => {
    chip.addEventListener("click", () => {
      const slug = chip.dataset.tagChip;
      if (selected.has(slug)) selected.delete(slug);
      else selected.add(slug);
      sync();
    });
  });

  // Exposed so a prefill (typeahead pick) can restore an exercise's tags.
  window.setExerciseTags = (slugs) => {
    selected = new Set((slugs || []).filter(Boolean));
    sync();
  };

  sync();
})();
