// app/web/static/js/body-map-render.js
//
// Lightweight renderer for the muscle-map geometry in body-map-data.js.
// Replaces the body-highlighter npm package: same interaction model (tap a
// region, get its slug back), but self-hosted so there's no CDN dependency
// and no per-polygon DOM rebuild on selection (keeps the CSS fill transition
// in base.html working, since setSelected mutates existing elements instead
// of tearing down and recreating them).

import { BODY_MAP } from "./body-map-data.js";

const SVG_NS = "http://www.w3.org/2000/svg";

function computeBounds(viewData, pad) {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const region of viewData) {
    for (const piece of region.pieces) {
      for (const [x, y] of piece) {
        if (x < minX) minX = x;
        if (x > maxX) maxX = x;
        if (y < minY) minY = y;
        if (y > maxY) maxY = y;
      }
    }
  }
  return { minX: minX - pad, minY: minY - pad, width: maxX - minX + pad * 2, height: maxY - minY + pad * 2 };
}

export function createBodyMap({ container, view = "anterior", bodyColor = "#404040", highlightColor = "#22c55e", style = {}, onClick }) {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.style.display = "block";
  for (const [prop, value] of Object.entries(style)) {
    svg.style[prop] = value;
  }

  let currentView = view;
  let selected = new Set();
  let polygonEls = []; // [{ el, slug }] for the clickable regions in the current view

  const render = () => {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    polygonEls = [];

    const data = BODY_MAP[currentView];
    const bounds = computeBounds(data, 6);
    svg.setAttribute("viewBox", `${bounds.minX} ${bounds.minY} ${bounds.width} ${bounds.height}`);

    for (const region of data) {
      for (const piece of region.pieces) {
        const polygon = document.createElementNS(SVG_NS, "polygon");
        polygon.setAttribute("points", piece.map(([x, y]) => `${x},${y}`).join(" "));
        const isSelected = region.slug && selected.has(region.slug);
        polygon.setAttribute("fill", isSelected ? highlightColor : bodyColor);
        if (region.slug) {
          polygon.style.cursor = "pointer";
          polygon.addEventListener("click", () => onClick && onClick({ muscle: region.slug }));
          polygonEls.push({ el: polygon, slug: region.slug });
        }
        svg.appendChild(polygon);
      }
    }
  };

  render();
  if (container) container.appendChild(svg);

  return {
    element: svg,
    setView(nextView) {
      currentView = nextView;
      render();
    },
    setSelected(slugs) {
      selected = new Set(slugs);
      for (const { el, slug } of polygonEls) {
        el.setAttribute("fill", selected.has(slug) ? highlightColor : bodyColor);
      }
    },
  };
}
