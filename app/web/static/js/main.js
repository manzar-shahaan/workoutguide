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
});
