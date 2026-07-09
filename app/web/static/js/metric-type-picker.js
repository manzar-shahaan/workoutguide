// app/web/static/js/metric-type-picker.js
//
// Metric-type toggle on the add/edit exercise forms: how the exercise is
// logged. "Weights & reps" (resistance) shows the muscle map + weight-unit
// + weight/reps set list; "Time & distance" (endurance) shows the
// distance-unit + duration/distance interval list instead. This is the
// *how you log it* axis -- the *what it is* axis (cardio/agility/...) is
// separate tag chips (tag-picker.js), and the *which muscles* axis is the
// region map.
//
// Runs immediately (script sits at the bottom of the page, after the form
// markup): window.setExerciseMetricType must exist before main.js's
// DOMContentLoaded handler tries to call it during a prefill.
(() => {
  const picker = document.querySelector("[data-metric-type-picker]");
  if (!picker) return;

  const metricInput = document.getElementById("metric_type");
  const buttons = picker.querySelectorAll("[data-metric-btn]");
  const regionWrapper = document.querySelector("[data-region-picker-wrapper]");
  const weightUnitWrapper = document.querySelector("[data-weight-unit-wrapper]");
  const distanceUnitWrapper = document.querySelector("[data-distance-unit-wrapper]");
  const strengthSetList = document.querySelector("[data-set-list]");
  const cardioSetList = document.querySelector("[data-cardio-set-list]");
  if (!metricInput || !buttons.length) return;

  const applyMetricType = (metricType) => {
    const isEndurance = metricType === "endurance";
    metricInput.value = isEndurance ? "endurance" : "resistance";
    metricInput.dispatchEvent(new Event("change", { bubbles: true }));
    buttons.forEach((btn) => {
      btn.classList.toggle("is-active", btn.dataset.metricBtn === metricInput.value);
    });

    // Regions stay a resistance-only concept so a run doesn't count toward
    // muscle freshness (same rule as before the tag split).
    if (regionWrapper) regionWrapper.classList.toggle("hidden", isEndurance);
    if (weightUnitWrapper) weightUnitWrapper.classList.toggle("hidden", isEndurance);
    if (distanceUnitWrapper) distanceUnitWrapper.classList.toggle("hidden", !isEndurance);
    if (strengthSetList) strengthSetList.classList.toggle("hidden", isEndurance);
    if (cardioSetList) cardioSetList.classList.toggle("hidden", !isEndurance);
  };

  buttons.forEach((btn) => {
    btn.addEventListener("click", () => applyMetricType(btn.dataset.metricBtn));
  });

  // Exposed so a prefill (typeahead pick / home cardio shortcut) can switch
  // the form's metric type after this widget has rendered.
  window.setExerciseMetricType = (metricType) => {
    if (metricType) applyMetricType(metricType);
  };

  applyMetricType(metricInput.value || "resistance");
})();
