// app/web/static/js/exercise-autosave.js
//
// Edit-exercise form auto-save: no Save button, edits land on disk on
// their own so navigating back mid-edit never loses anything. Debounces
// ~700ms after the last change, then POSTs the whole form as the picker
// scripts (set-list.js, region-picker.js, tag-picker.js, ...) already
// dispatch a bubbling "change" on their hidden inputs whenever they write
// to them. A save that fails validation (e.g. every set row cleared) just
// reports why in the status chip -- the server never writes on a rejected
// submit, so the last good state stays on disk.

(() => {
  // Attached immediately (not gated on "load" like the autosave wiring
  // below) so the confirm dialog is live as soon as the button exists.
  // `deleting` is read by flushOnUnload() further down to skip the
  // unload-safety save -- otherwise a pending edit's keepalive POST could
  // race the delete and try to write set rows for an exercise that's
  // mid-deletion.
  let deleting = false;
  const deleteForm = document.getElementById("deleteExerciseForm");
  if (deleteForm) {
    deleteForm.addEventListener("submit", (event) => {
      if (!confirm("Delete this exercise?")) {
        event.preventDefault();
        return;
      }
      deleting = true;
    });
  }

  // Listener attachment waits for "load" (not DOMContentLoaded), because
  // region-picker.js is a deferred module whose own DOMContentLoaded
  // handler -- and its initial, no-op sync() call -- runs after this
  // classic script has already executed. Attaching here immediately would
  // catch that no-op sync as a "change" and fire a spurious save right
  // after the page opens.
  window.addEventListener("load", () => {
    const form = document.getElementById("exerciseEditForm");
    if (!form) return;

    const autosaveUrl = form.dataset.autosaveUrl;
    const statusEl = document.getElementById("autosaveStatus");
    const backLink = document.getElementById("backToWorkoutLink");
    const doneLink = document.getElementById("doneEditingLink");
    const dateInput = document.getElementById("date");

    let saveTimer = null;
    let dirty = false;

    const setStatus = (text, isError) => {
      if (!statusEl) return;
      statusEl.textContent = text;
      statusEl.classList.toggle("text-red-400", !!isError);
      statusEl.classList.toggle("text-neutral-500", !isError);
    };

    const applyWorkoutUrl = (workoutUrl) => {
      if (!workoutUrl) return;
      if (backLink) backLink.href = workoutUrl;
      if (doneLink) doneLink.href = workoutUrl;
    };

    const doSave = () => {
      dirty = false;
      setStatus("Saving…", false);
      fetch(autosaveUrl, {
        method: "POST",
        headers: { "X-Requested-With": "XMLHttpRequest" },
        body: new FormData(form),
      })
        .then((res) => res.json())
        .then((data) => {
          if (data.ok) {
            setStatus("Saved", false);
            applyWorkoutUrl(data.workout_url);
          } else {
            setStatus(data.error || "Couldn't save", true);
          }
        })
        .catch(() => setStatus("Couldn't save — check your connection", true));
    };

    const scheduleSave = (immediate) => {
      dirty = true;
      setStatus("Editing…", false);
      if (saveTimer) clearTimeout(saveTimer);
      if (immediate) {
        saveTimer = null;
        doSave();
      } else {
        saveTimer = setTimeout(doSave, 700);
      }
    };

    form.addEventListener("input", () => scheduleSave(false));
    form.addEventListener("change", (event) => {
      // The date picker only fires "change" once a full date is chosen
      // (not per-keystroke), and a date edit can move the exercise to a
      // different workout -- save it right away so the back/done links
      // repoint sooner.
      scheduleSave(event.target === dateInput);
    });

    // Safety net for navigating away (tapping back/done, browser back,
    // closing the PWA) mid-debounce: flush synchronously with keepalive so
    // the request survives the page unloading, without blocking the
    // navigation itself.
    const flushOnUnload = () => {
      if (!dirty || deleting) return;
      if (saveTimer) {
        clearTimeout(saveTimer);
        saveTimer = null;
      }
      dirty = false;
      fetch(autosaveUrl, {
        method: "POST",
        headers: { "X-Requested-With": "XMLHttpRequest" },
        body: new FormData(form),
        keepalive: true,
      }).catch(() => {});
    };

    window.addEventListener("pagehide", flushOnUnload);
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "hidden") flushOnUnload();
    });
  });
})();
