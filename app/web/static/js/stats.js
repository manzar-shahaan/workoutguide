// app/web/static/js/stats.js

document.addEventListener("DOMContentLoaded", () => {
  const config = window.statsConfig;
  if (!config) return;

  const chartCanvas = document.getElementById("muscleChart");
  const chartEmptyState = document.getElementById("chartEmptyState");
  const muscleSelect = document.getElementById("muscleSelect");
  const rangeSelect = document.getElementById("rangeSelect");
  const customFields = document.getElementById("customRangeFields");
  const applyButton = document.getElementById("applyRange");
  const customStart = document.getElementById("customStart");
  const customEnd = document.getElementById("customEnd");

  const toPreferred = (kgValue) => {
    if (kgValue === null || kgValue === undefined) return null;
    return config.preferredUnit === "lb" ? kgValue / 0.45359237 : kgValue;
  };

  let chart = null;

  const setEmptyState = (message) => {
    if (!chartEmptyState) return;
    chartEmptyState.textContent = message;
    chartEmptyState.classList.remove("hidden");
    if (chartCanvas) {
      chartCanvas.classList.add("hidden");
    }
  };

  const clearEmptyState = () => {
    if (!chartEmptyState) return;
    chartEmptyState.classList.add("hidden");
    if (chartCanvas) {
      chartCanvas.classList.remove("hidden");
    }
  };

  const buildChart = (labels, values) => {
    if (!chartCanvas) return;
    if (typeof Chart === "undefined") {
      setEmptyState("Chart library failed to load. Check your network connection.");
      return;
    }

    const converted = values.map((value) =>
      value === null ? null : Number(toPreferred(value).toFixed(2))
    );

    const datasetLabel =
      config.preferredUnit === "lb" ? "Weight (lb)" : "Weight (kg)";

    const hasData = converted.some((value) => value !== null && !Number.isNaN(value));
    if (!hasData) {
      setEmptyState("No weight data for this muscle and range yet.");
      if (chart) {
        chart.destroy();
        chart = null;
      }
      return;
    }

    clearEmptyState();
    if (chart) {
      chart.data.labels = labels;
      chart.data.datasets[0].data = converted;
      chart.data.datasets[0].label = datasetLabel;
      chart.update();
      return;
    }

    chart = new Chart(chartCanvas, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: datasetLabel,
            data: converted,
            borderColor: "#10b981",
            backgroundColor: "rgba(16, 185, 129, 0.2)",
            tension: 0.3,
            pointRadius: 3,
          },
        ],
      },
      options: {
        responsive: true,
        scales: {
          x: {
            ticks: { color: "#94a3b8" },
            grid: { color: "rgba(148, 163, 184, 0.1)" },
          },
          y: {
            ticks: { color: "#94a3b8" },
            grid: { color: "rgba(148, 163, 184, 0.1)" },
          },
        },
        plugins: {
          legend: {
            labels: {
              color: "#e2e8f0",
            },
          },
        },
      },
    });
  };

  const fetchData = () => {
    if (!config.chartMuscle || !muscleSelect) return;
    const muscleId = muscleSelect.value;
    const range = rangeSelect ? rangeSelect.value : config.chartRange;

    const url = new URL(config.endpoint, window.location.origin);
    url.searchParams.set("muscle_id", muscleId);
    url.searchParams.set("range", range);

    if (range === "custom" && customStart && customEnd) {
      if (customStart.value && customEnd.value) {
        url.searchParams.set("start", customStart.value);
        url.searchParams.set("end", customEnd.value);
      }
    }

    fetch(url.toString())
      .then((response) => response.json())
      .then((data) => {
        buildChart(data.labels || [], data.values || []);
      })
      .catch(() => {
        setEmptyState("Unable to load chart data.");
      });
  };

  if (chartCanvas) {
    buildChart(config.initial.labels || [], config.initial.values || []);
  }

  if (rangeSelect && customFields) {
    rangeSelect.addEventListener("change", () => {
      const isCustom = rangeSelect.value === "custom";
      customFields.classList.toggle("hidden", !isCustom);
      if (!isCustom) {
        fetchData();
      }
    });
  }

  if (muscleSelect) {
    muscleSelect.addEventListener("change", fetchData);
  }

  if (applyButton) {
    applyButton.addEventListener("click", (event) => {
      event.preventDefault();
      fetchData();
    });
  }

  const toggles = document.querySelectorAll("[data-toggle-target]");
  toggles.forEach((button) => {
    button.addEventListener("click", () => {
      const targetId = button.getAttribute("data-toggle-target");
      const target = document.getElementById(targetId);
      if (!target) return;
      const isHidden = target.classList.contains("hidden");
      target.classList.toggle("hidden", !isHidden);
      button.textContent = isHidden ? "Show less" : "Show all";
    });
  });
});
