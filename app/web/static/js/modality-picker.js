// app/web/static/js/modality-picker.js
//
// Exercise-type toggle on the add/edit exercise forms. Strength/mobility/
// plyometrics all target body regions and log weight/reps (the map and
// weight-unit/set-list stay visible); cardio swaps those for a
// Steady/HIIT/Intervals/Sprints pick plus duration/distance intervals
// instead, since "which muscle" and "how much weight" aren't the useful
// classification for a run.

// Runs immediately (not on DOMContentLoaded): this script tag sits at the
// bottom of the page, after the form markup, so its target elements
// already exist -- and window.setExerciseModality must be defined before
// main.js's DOMContentLoaded handler (registered earlier, in base.html)
// tries to call it during a typeahead/quick-list prefill.
(() => {
  const picker = document.querySelector("[data-modality-picker]");
  if (!picker) return;

  const modalityInput = document.getElementById("modality");
  const cardioTargetInput = document.getElementById("cardio_target");
  const buttons = picker.querySelectorAll("[data-modality-btn]");
  const cardioWrapper = picker.querySelector("[data-cardio-target-wrapper]");
  const cardioSelect = picker.querySelector("[data-cardio-target-select]");
  const regionWrapper = document.querySelector("[data-region-picker-wrapper]");
  const weightUnitWrapper = document.querySelector("[data-weight-unit-wrapper]");
  const distanceUnitWrapper = document.querySelector("[data-distance-unit-wrapper]");
  const strengthSetList = document.querySelector("[data-set-list]");
  const cardioSetList = document.querySelector("[data-cardio-set-list]");
  if (!modalityInput || !cardioTargetInput || !buttons.length) return;

  const applyModality = (modality) => {
    modalityInput.value = modality;
    buttons.forEach((btn) => {
      btn.classList.toggle("is-active", btn.dataset.modalityBtn === modality);
    });

    const isCardio = modality === "cardio";
    if (cardioWrapper) cardioWrapper.classList.toggle("hidden", !isCardio);
    if (regionWrapper) regionWrapper.classList.toggle("hidden", isCardio);
    if (weightUnitWrapper) weightUnitWrapper.classList.toggle("hidden", isCardio);
    if (distanceUnitWrapper) distanceUnitWrapper.classList.toggle("hidden", !isCardio);
    if (strengthSetList) strengthSetList.classList.toggle("hidden", isCardio);
    if (cardioSetList) cardioSetList.classList.toggle("hidden", !isCardio);

    if (!isCardio) {
      cardioTargetInput.value = "";
    } else if (cardioSelect && !cardioTargetInput.value) {
      cardioTargetInput.value = cardioSelect.value;
    }
  };

  buttons.forEach((btn) => {
    btn.addEventListener("click", () => applyModality(btn.dataset.modalityBtn));
  });

  if (cardioSelect) {
    if (cardioTargetInput.value) cardioSelect.value = cardioTargetInput.value;
    cardioSelect.addEventListener("change", () => {
      cardioTargetInput.value = cardioSelect.value;
    });
  }

  // Exposed so a prefill (typeahead pick / cardio quick-list / muscle-map
  // handoff) can switch the form's modality after this widget has already
  // rendered, same pattern as window.setExerciseSets / window.setCardioSets.
  window.setExerciseModality = (modality, cardioTarget) => {
    if (!modality) return;
    applyModality(modality);
    if (cardioTarget && cardioSelect) {
      cardioSelect.value = cardioTarget;
      cardioTargetInput.value = cardioTarget;
    }
  };

  applyModality(modalityInput.value || "strength");
})();
