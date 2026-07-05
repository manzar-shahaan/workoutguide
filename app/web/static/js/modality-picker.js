// app/web/static/js/modality-picker.js
//
// Exercise-type toggle on the add/edit exercise forms. Strength/mobility/
// plyometrics all target body regions (the map stays visible); cardio
// swaps the map for a Steady/HIIT/Intervals/Sprints pick instead, since
// "which muscle" isn't the useful classification for a run.

document.addEventListener("DOMContentLoaded", () => {
  const picker = document.querySelector("[data-modality-picker]");
  if (!picker) return;

  const modalityInput = document.getElementById("modality");
  const cardioTargetInput = document.getElementById("cardio_target");
  const buttons = picker.querySelectorAll("[data-modality-btn]");
  const cardioWrapper = picker.querySelector("[data-cardio-target-wrapper]");
  const cardioSelect = picker.querySelector("[data-cardio-target-select]");
  const regionWrapper = document.querySelector("[data-region-picker-wrapper]");
  if (!modalityInput || !cardioTargetInput || !buttons.length) return;

  const applyModality = (modality) => {
    modalityInput.value = modality;
    buttons.forEach((btn) => {
      btn.classList.toggle("is-active", btn.dataset.modalityBtn === modality);
    });

    const isCardio = modality === "cardio";
    if (cardioWrapper) cardioWrapper.classList.toggle("hidden", !isCardio);
    if (regionWrapper) regionWrapper.classList.toggle("hidden", isCardio);

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

  applyModality(modalityInput.value || "strength");
});
