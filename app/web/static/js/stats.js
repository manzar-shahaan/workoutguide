// app/web/static/js/stats.js

document.addEventListener("DOMContentLoaded", () => {
  const config = window.statsConfig;
  if (!config) return;

  const chartCanvas = document.getElementById("muscleChart");
  const chartEmptyState = document.getElementById("chartEmptyState");
  const muscleSelect = document.getElementById("muscleSelect");
  const exerciseDropdown = document.querySelector("[data-exercise-dropdown]");
  const exerciseIdsInput = document.getElementById("exerciseIds");
  const metricSelect = document.getElementById("metricSelect");
  const rangeSelect = document.getElementById("rangeSelect");
  const customFields = document.getElementById("customRangeFields");
  const applyButton = document.getElementById("applyRange");
  const customStart = document.getElementById("customStart");
  const customEnd = document.getElementById("customEnd");
  const resetZoom = document.getElementById("resetZoom");
  const viewButtons = document.querySelectorAll("[data-view-button]");
  const viewBlocks = document.querySelectorAll("[data-view-block]");

  const DEFAULT_ACCENT = "#10b981";
  const COLOR_REGEX = /^#[0-9a-fA-F]{6}$/;
  const isTouch =
    window.matchMedia
      ? window.matchMedia("(hover: none), (pointer: coarse)").matches
      : "ontouchstart" in window;

  const toPreferred = (kgValue) => {
    if (kgValue === null || kgValue === undefined) return null;
    return config.preferredUnit === "lb" ? kgValue / 0.45359237 : kgValue;
  };

  const METRIC_LABELS = {
    weight: (unit) => (unit === "lb" ? "Weight (lb)" : "Weight (kg)"),
    avg_reps: () => "Avg reps",
    max_reps: () => "Max reps",
    volume: (unit) => (unit === "lb" ? "Est. volume (lb)" : "Est. volume (kg)"),
  };
  const METRIC_PRECISION = {
    weight: 2,
    avg_reps: 1,
    max_reps: 0,
    volume: 2,
  };

  let chart = null;
  let emptyMessage = "No data for this muscle and range yet.";
  if (config.chartExerciseIds && config.chartExerciseIds.length) {
    emptyMessage = "No data for the selected exercises and range yet.";
  } else if (config.chartExercise) {
    emptyMessage = "No data for this exercise and range yet.";
  }

  const getSelectedExerciseIds = () => {
    if (!exerciseIdsInput) return [];
    const raw = exerciseIdsInput.value || "";
    return raw
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);
  };

  const setSelectedExerciseIds = (ids) => {
    if (!exerciseIdsInput) return;
    exerciseIdsInput.value = ids.join(",");
  };

  const updateExerciseLabel = (count, total) => {
    if (!exerciseDropdown) return;
    const label = exerciseDropdown.querySelector("[data-exercise-label]");
    if (!label) return;
    if (!total) {
      label.textContent = "All exercises";
      return;
    }
    if (!count) {
      label.textContent = "All exercises";
      return;
    }
    label.textContent = `${count} selected`;
  };

  const renderExerciseOptions = (items, selectedIds) => {
    if (!exerciseDropdown) return;
    const list = exerciseDropdown.querySelector("[data-exercise-list]");
    if (!list) return;
    list.innerHTML = "";
    items.forEach((item) => {
      const wrapper = document.createElement("label");
      wrapper.className =
        "flex items-center gap-2 rounded-md px-2 py-1 hover:bg-slate-900";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.value = String(item.id);
      checkbox.checked = selectedIds.includes(String(item.id));
      checkbox.addEventListener("change", () => {
        const updated = Array.from(list.querySelectorAll("input[type='checkbox']"))
          .filter((node) => node.checked)
          .map((node) => node.value);
        setSelectedExerciseIds(updated);
        updateExerciseLabel(updated.length, items.length);
        fetchData();
      });
      const text = document.createElement("span");
      text.textContent = item.name;
      wrapper.appendChild(checkbox);
      wrapper.appendChild(text);
      list.appendChild(wrapper);
    });
    updateExerciseLabel(selectedIds.length, items.length);
  };
  const zoomPlugin =
    window.ChartZoom || window.Zoom || window["chartjs-plugin-zoom"];
  if (typeof Chart !== "undefined" && zoomPlugin && Chart.register) {
    Chart.register(zoomPlugin);
  }

  const updateResetZoomState = () => {
    if (!resetZoom) return;
    const canReset = chart && typeof chart.resetZoom === "function";
    resetZoom.disabled = !canReset;
    resetZoom.title = canReset ? "" : "Zoom unavailable";
  };

  const normalizeColor = (color) => {
    const candidate = (color || "").trim();
    return COLOR_REGEX.test(candidate) ? candidate : DEFAULT_ACCENT;
  };

  const hexToRgb = (hex) => {
    const normalized = normalizeColor(hex).slice(1);
    return {
      r: parseInt(normalized.slice(0, 2), 16),
      g: parseInt(normalized.slice(2, 4), 16),
      b: parseInt(normalized.slice(4, 6), 16),
    };
  };

  const rgbaFromHex = (hex, alpha) => {
    const rgb = hexToRgb(hex);
    return `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, ${alpha})`;
  };

  const accentForSelection = () => {
    if (!muscleSelect) return DEFAULT_ACCENT;
    const selected = muscleSelect.options[muscleSelect.selectedIndex];
    return normalizeColor(selected ? selected.dataset.color : null);
  };

  const fillGradient = (chartRef, accentColor) => {
    if (!chartRef) return rgbaFromHex(accentColor, 0.2);
    const { ctx, chartArea } = chartRef;
    if (!chartArea) return rgbaFromHex(accentColor, 0.2);
    const gradient = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
    gradient.addColorStop(0, rgbaFromHex(accentColor, 0.35));
    gradient.addColorStop(1, rgbaFromHex(accentColor, 0.02));
    return gradient;
  };

  const setCalendarView = (view) => {
    if (!viewButtons.length) return;
    const activeView = view === "week" ? "week" : "month";

    viewBlocks.forEach((block) => {
      const blockView = block.getAttribute("data-view-block");
      block.classList.toggle("hidden", blockView !== activeView);
    });

    viewButtons.forEach((button) => {
      const buttonView = button.getAttribute("data-view-button");
      const isActive = buttonView === activeView;
      button.classList.toggle("bg-emerald-500", isActive);
      button.classList.toggle("text-black", isActive);
      button.classList.toggle("border", !isActive);
      button.classList.toggle("border-slate-700", !isActive);
      button.classList.toggle("bg-slate-900", !isActive);
      button.classList.toggle("text-slate-200", !isActive);
    });
  };

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

  const buildChart = (labels, values, metric) => {
    if (!chartCanvas) return;
    if (typeof Chart === "undefined") {
      setEmptyState("Chart library failed to load. Check your network connection.");
      return;
    }

    const normalizedMetric = METRIC_LABELS[metric] ? metric : "weight";
    const precision = METRIC_PRECISION[normalizedMetric] ?? 2;
    const converted = values.map((value) => {
      if (value === null || value === undefined) return null;
      const base = ["weight", "volume"].includes(normalizedMetric)
        ? toPreferred(value)
        : value;
      return Number(Number(base).toFixed(precision));
    });

    const labelFn = METRIC_LABELS[normalizedMetric] || METRIC_LABELS.weight;
    const datasetLabel = labelFn(config.preferredUnit);
    const accentColor = accentForSelection();
    const maxTicks = isTouch ? 4 : 6;
    const pointRadius = isTouch ? 5 : 4;
    const pointHoverRadius = isTouch ? 7 : 7;
    const pointHitRadius = isTouch ? 18 : 12;
    const interactionMode = isTouch ? "nearest" : "index";
    const numericValues = converted.filter((value) => value !== null && !Number.isNaN(value));
    let yMin = null;
    let yMax = null;
    if (numericValues.length) {
      const min = Math.min(...numericValues);
      const max = Math.max(...numericValues);
      const range = Math.max(max - min, min === 0 && max === 0 ? 1 : Math.abs(max || 1));
      const pad = range * 0.08;
      yMin = min - pad;
      yMax = max + pad;
    }

    const hasData = converted.some((value) => value !== null && !Number.isNaN(value));
    if (!hasData) {
      setEmptyState(emptyMessage);
      if (chart) {
        chart.destroy();
        chart = null;
      }
      updateResetZoomState();
      return;
    }

    clearEmptyState();
    if (chart) {
      chart.data.labels = labels;
      const dataset = chart.data.datasets[0];
      dataset.data = converted;
      dataset.label = datasetLabel;
      dataset.borderColor = accentColor;
      dataset.pointBorderColor = accentColor;
      dataset.pointBackgroundColor = rgbaFromHex(accentColor, 0.25);
      dataset.pointRadius = pointRadius;
      dataset.pointHoverRadius = pointHoverRadius;
      dataset.pointBorderWidth = 2.5;
      dataset.pointHitRadius = pointHitRadius;
      dataset.backgroundColor = (context) =>
        fillGradient(context.chart, accentColor);
      if (chart.options.scales?.x?.ticks) {
        chart.options.scales.x.ticks.maxTicksLimit = maxTicks;
      }
      if (chart.options.scales?.x) {
        chart.options.scales.x.offset = true;
      }
      if (chart.options.scales?.y) {
        chart.options.scales.y.suggestedMin = yMin;
        chart.options.scales.y.suggestedMax = yMax;
      }
      if (chart.options.interaction) {
        chart.options.interaction.mode = interactionMode;
      }
      chart.update();
      updateResetZoomState();
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
            borderColor: accentColor,
            backgroundColor: (context) => fillGradient(context.chart, accentColor),
            borderWidth: 2.5,
            tension: 0.35,
            fill: true,
            pointRadius,
            pointHoverRadius,
            pointBackgroundColor: rgbaFromHex(accentColor, 0.25),
            pointBorderColor: accentColor,
            pointBorderWidth: 2.5,
            pointHitRadius,
            spanGaps: true,
          },
        ],
      },
      options: {
        responsive: true,
        events: ["mousemove", "mouseout", "click", "touchstart", "touchmove"],
        interaction: {
          mode: interactionMode,
          intersect: false,
          axis: "x",
        },
        layout: {
          padding: {
            top: 8,
            right: 12,
            bottom: 4,
            left: 8,
          },
        },
        scales: {
          x: {
            offset: true,
            ticks: {
              color: "#94a3b8",
              maxTicksLimit: maxTicks,
            },
            grid: {
              display: false,
            },
          },
          y: {
            suggestedMin: yMin,
            suggestedMax: yMax,
            ticks: {
              color: "#94a3b8",
              padding: 6,
            },
            grid: {
              color: "rgba(148, 163, 184, 0.12)",
            },
          },
        },
        plugins: {
          legend: {
            display: false,
          },
          tooltip: {
            backgroundColor: "rgba(15, 23, 42, 0.96)",
            borderColor: "rgba(148, 163, 184, 0.35)",
            borderWidth: 1,
            titleColor: "#e2e8f0",
            bodyColor: "#e2e8f0",
            displayColors: false,
            padding: 10,
          },
          zoom: {
            zoom: {
              wheel: { enabled: !isTouch },
              pinch: { enabled: true },
              mode: "x",
            },
            pan: {
              enabled: true,
              mode: "x",
            },
          },
        },
      },
    });
    updateResetZoomState();
  };

  const fetchData = () => {
    if (!config.chartMuscle || !muscleSelect) return;
    const muscleId = muscleSelect.value;
    const exerciseIds = getSelectedExerciseIds();
    const range = rangeSelect ? rangeSelect.value : config.chartRange;
    const metric = metricSelect ? metricSelect.value : config.chartMetric || "weight";

    const url = new URL(config.endpoint, window.location.origin);
    url.searchParams.set("muscle_id", muscleId);
    url.searchParams.set("range", range);
    if (exerciseIds.length) {
      url.searchParams.set("exercise_ids", exerciseIds.join(","));
      emptyMessage =
        exerciseIds.length > 1
          ? "No data for the selected exercises and range yet."
          : "No data for this exercise and range yet.";
    } else {
      emptyMessage = "No data for this muscle and range yet.";
    }
    url.searchParams.set("metric", metric);

    if (range === "custom" && customStart && customEnd) {
      if (customStart.value && customEnd.value) {
        url.searchParams.set("start", customStart.value);
        url.searchParams.set("end", customEnd.value);
      }
    }

    fetch(url.toString())
      .then((response) => response.json())
      .then((data) => {
        buildChart(data.labels || [], data.values || [], metric);
      })
      .catch(() => {
        setEmptyState("Unable to load chart data.");
      });
  };

  if (chartCanvas) {
    buildChart(
      config.initial.labels || [],
      config.initial.values || [],
      config.chartMetric || "weight"
    );
  }

  if (Array.isArray(config.chartExerciseIds)) {
    setSelectedExerciseIds(config.chartExerciseIds.map((value) => String(value)));
  } else if (typeof config.chartExercise === "number") {
    setSelectedExerciseIds([String(config.chartExercise)]);
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

  if (metricSelect) {
    metricSelect.addEventListener("change", () => {
      fetchData();
    });
  }

  if (muscleSelect) {
    muscleSelect.addEventListener("change", () => {
      if (exerciseDropdown && config.exerciseEndpoint) {
        const url = new URL(config.exerciseEndpoint, window.location.origin);
        url.searchParams.set("muscle_id", muscleSelect.value);
        setSelectedExerciseIds([]);
        const selected = new Set();
        fetch(url.toString())
          .then((response) => response.json())
          .then((data) => {
            const items = data.items || [];
            renderExerciseOptions(items, Array.from(selected));
          })
          .catch(() => {
            renderExerciseOptions([], []);
          })
          .finally(() => {
            fetchData();
          });
        return;
      }
      fetchData();
    });
  }

  if (exerciseDropdown) {
    const selectAll = exerciseDropdown.querySelector("[data-exercise-select-all]");
    const clearAll = exerciseDropdown.querySelector("[data-exercise-clear]");
    const list = exerciseDropdown.querySelector("[data-exercise-list]");

    if (selectAll && list) {
      selectAll.addEventListener("click", () => {
        const boxes = Array.from(list.querySelectorAll("input[type='checkbox']"));
        boxes.forEach((box) => {
          box.checked = true;
        });
        const ids = boxes.map((box) => box.value);
        setSelectedExerciseIds(ids);
        updateExerciseLabel(ids.length, boxes.length);
        fetchData();
      });
    }

    if (clearAll && list) {
      clearAll.addEventListener("click", () => {
        const boxes = Array.from(list.querySelectorAll("input[type='checkbox']"));
        boxes.forEach((box) => {
          box.checked = false;
        });
        setSelectedExerciseIds([]);
        updateExerciseLabel(0, boxes.length);
        fetchData();
      });
    }

    if (list) {
      const initialIds = Array.from(list.querySelectorAll("input[type='checkbox']"))
        .filter((box) => box.checked)
        .map((box) => box.value);
      setSelectedExerciseIds(initialIds);
      updateExerciseLabel(
        initialIds.length,
        list.querySelectorAll("input[type='checkbox']").length
      );
      list.addEventListener("change", () => {
        const ids = Array.from(list.querySelectorAll("input[type='checkbox']"))
          .filter((box) => box.checked)
          .map((box) => box.value);
        setSelectedExerciseIds(ids);
        updateExerciseLabel(
          ids.length,
          list.querySelectorAll("input[type='checkbox']").length
        );
        fetchData();
      });
    }

    if (config.exerciseEndpoint && muscleSelect) {
      const url = new URL(config.exerciseEndpoint, window.location.origin);
      url.searchParams.set("muscle_id", muscleSelect.value);
      fetch(url.toString())
        .then((response) => response.json())
        .then((data) => {
          const items = data.items || [];
          renderExerciseOptions(items, getSelectedExerciseIds());
        })
        .catch(() => {
          renderExerciseOptions([], []);
        });
    }

    document.addEventListener("click", (event) => {
      if (!exerciseDropdown.contains(event.target)) {
        exerciseDropdown.removeAttribute("open");
      }
    });
  }

  if (applyButton) {
    applyButton.addEventListener("click", (event) => {
      event.preventDefault();
      fetchData();
    });
  }

  if (resetZoom) {
    resetZoom.addEventListener("click", () => {
      if (chart && typeof chart.resetZoom === "function") {
        chart.resetZoom();
      }
    });
  }

  if (viewButtons.length) {
    setCalendarView(config.view || "month");
    viewButtons.forEach((button) => {
      button.addEventListener("click", () => {
        const targetView = button.getAttribute("data-view-button");
        setCalendarView(targetView || "month");
      });
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
