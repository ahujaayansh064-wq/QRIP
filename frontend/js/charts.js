// Animated SVG infographics. Every chart here draws itself in the direction the
// analysis flows, so motion carries meaning rather than decorating the page.

import { h } from "./ui.js";

const NS = "http://www.w3.org/2000/svg";

export function svg(viewBox, inner, attrs) {
  const extra = Object.entries(attrs || {})
    .map(([key, value]) => " " + key + '="' + value + '"').join("");
  return h("div", {
    class: "overflow-hidden",
    html: '<svg viewBox="' + viewBox + '" width="100%" xmlns="' + NS + '"'
      + ' preserveAspectRatio="xMidYMid meet"' + extra + ">" + inner + "</svg>",
  });
}

export function esc(text) {
  return String(text === null || text === undefined ? "" : text)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// --- numbers -------------------------------------------------------------

export function countUp(node, target, options) {
  const settings = options || {};
  const duration = settings.duration || 1100;
  const decimals = settings.decimals || 0;
  const suffix = settings.suffix || "";
  const start = performance.now();
  const from = Number(settings.from || 0);
  const to = Number(target || 0);
  function step(now) {
    const t = Math.min(1, (now - start) / duration);
    const eased = 1 - Math.pow(1 - t, 3);
    const value = from + (to - from) * eased;
    node.textContent = value.toFixed(decimals) + suffix;
    if (t < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
  return node;
}

export function counter(value, options) {
  const node = h("span", { class: "count", text: "0" });
  const settings = options || {};
  const final = Number(value || 0).toFixed(settings.decimals || 0) + (settings.suffix || "");
  // Whatever happens to the animation — hidden tab, no observer, an element that
  // never intersects — the number must end up showing its value.
  setTimeout(() => {
    if (node.textContent === "0" && final !== "0") node.textContent = final;
  }, 2500);
  if (typeof IntersectionObserver !== "function") {
    setTimeout(() => countUp(node, value, options), 60);
    return node;
  }
  const observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (entry.isIntersecting) {
        countUp(node, value, options);
        observer.disconnect();
      }
    }
  }, { threshold: 0.4 });
  // setTimeout rather than rAF: frames are suspended while a tab is hidden,
  // and a number that never starts counting reads as a broken page.
  setTimeout(() => {
    if (node.isConnected) observer.observe(node);
    else setTimeout(() => countUp(node, value, options), 300);
  }, 0);
  return node;
}

// --- donut / ring --------------------------------------------------------

export function ring(value, label, color) {
  const pct = Math.max(0, Math.min(1, Number(value) || 0));
  const radius = 52;
  const circumference = 2 * Math.PI * radius;
  const stroke = color || "#2B4570";
  const inner = [
    '<circle cx="70" cy="70" r="' + radius + '" fill="none" stroke="#E4E1D8" stroke-width="10"/>',
    '<circle cx="70" cy="70" r="' + radius + '" fill="none" stroke="' + stroke + '"',
    ' stroke-width="10" stroke-linecap="round" transform="rotate(-90 70 70)"',
    ' stroke-dasharray="' + circumference + '" stroke-dashoffset="' + circumference + '">',
    '<animate attributeName="stroke-dashoffset" from="' + circumference + '" to="'
      + (circumference * (1 - pct)) + '" dur="1.1s" fill="freeze"',
    ' calcMode="spline" keySplines="0.22 0.61 0.36 1" keyTimes="0;1"/></circle>',
    '<text x="70" y="70" text-anchor="middle" font-size="26" font-family="Georgia, serif"',
    ' fill="#1C1D21" dy="4">' + Math.round(pct * 100) + "%</text>",
    label ? '<text x="70" y="70" text-anchor="middle" font-size="9" fill="#6B6D76" dy="22">'
      + esc(label) + "</text>" : "",
  ].join("");
  return svg("0 0 140 140", inner, { style: "max-width:140px" });
}

// --- bars ----------------------------------------------------------------

export function barChart(items, options) {
  const settings = options || {};
  const max = Math.max(1, ...items.map((item) => item.value));
  const rowHeight = settings.rowHeight || 26;
  const width = 520;
  const labelWidth = settings.labelWidth || 170;
  const parts = [];
  items.forEach((item, i) => {
    const y = i * rowHeight;
    const barWidth = ((width - labelWidth - 46) * item.value) / max;
    const color = item.color || "#2B4570";
    parts.push('<text x="0" y="' + (y + 14) + '" font-size="11" fill="#1C1D21">'
      + esc(truncate(item.label, 26)) + "</text>");
    parts.push('<rect x="' + labelWidth + '" y="' + (y + 4) + '" height="12" rx="2" fill="'
      + color + '" fill-opacity="0.85" width="0">'
      + '<animate attributeName="width" from="0" to="' + barWidth + '" dur="0.8s"'
      + ' begin="' + (i * 0.05) + 's" fill="freeze" calcMode="spline"'
      + ' keySplines="0.22 0.61 0.36 1" keyTimes="0;1"/></rect>');
    parts.push('<text x="' + (labelWidth + barWidth + 6) + '" y="' + (y + 14)
      + '" font-size="10" fill="#6B6D76">' + esc(item.display || item.value) + "</text>");
  });
  return svg("0 0 " + width + " " + items.length * rowHeight, parts.join(""));
}

function truncate(text, limit) {
  const value = String(text || "");
  return value.length > limit ? value.slice(0, limit - 1) + "…" : value;
}

// --- code network (radial, curved edges) ---------------------------------

export function codeNetwork(nodes, edges, options) {
  const settings = options || {};
  const size = settings.size || 640;
  const centre = size / 2;
  const radius = centre - (settings.margin || 96);
  const shown = nodes.slice(0, settings.limit || 22);
  const index = new Map();
  const positions = shown.map((node, i) => {
    const angle = (i / shown.length) * Math.PI * 2 - Math.PI / 2;
    const point = {
      id: node.id, label: node.label, color: node.color || "#2B4570",
      count: node.count || 1,
      x: centre + Math.cos(angle) * radius,
      y: centre + Math.sin(angle) * radius,
      angle,
    };
    index.set(node.id, point);
    return point;
  });

  const maxWeight = Math.max(1, ...edges.map((edge) => edge.weight || 1));
  const arcs = [];
  edges.forEach((edge, i) => {
    const a = index.get(edge.source);
    const b = index.get(edge.target);
    if (!a || !b) return;
    const weight = edge.weight || 1;
    const opacity = 0.12 + 0.5 * (weight / maxWeight);
    const path = "M" + a.x + " " + a.y + " Q " + centre + " " + centre + " " + b.x + " " + b.y;
    arcs.push('<path d="' + path + '" fill="none" stroke="' + (edge.color || "#2B4570")
      + '" stroke-opacity="' + opacity.toFixed(3) + '" stroke-width="'
      + (0.6 + 2.4 * (weight / maxWeight)).toFixed(2) + '" stroke-dasharray="1400"'
      + ' stroke-dashoffset="1400"><animate attributeName="stroke-dashoffset" from="1400"'
      + ' to="0" dur="1.2s" begin="' + (0.02 * i).toFixed(2) + 's" fill="freeze"/></path>');
  });

  const maxCount = Math.max(1, ...positions.map((p) => p.count));
  const dots = positions.map((point, i) => {
    const r = 4 + 9 * Math.sqrt(point.count / maxCount);
    const anchor = Math.cos(point.angle) > 0.15 ? "start"
      : Math.cos(point.angle) < -0.15 ? "end" : "middle";
    const lx = point.x + Math.cos(point.angle) * (r + 7);
    const ly = point.y + Math.sin(point.angle) * (r + 7) + 4;
    return '<g opacity="0"><animate attributeName="opacity" from="0" to="1" dur="0.5s" begin="'
      + (0.3 + i * 0.04).toFixed(2) + 's" fill="freeze"/>'
      + '<circle cx="' + point.x + '" cy="' + point.y + '" r="' + r.toFixed(1)
      + '" fill="' + point.color + '" fill-opacity="0.9"/>'
      + '<text x="' + lx.toFixed(1) + '" y="' + ly.toFixed(1) + '" font-size="10"'
      + ' text-anchor="' + anchor + '" fill="#1C1D21">'
      + esc(truncate(point.label, 22)) + "</text></g>";
  }).join("");

  return svg("0 0 " + size + " " + size, arcs.join("") + dots,
             { style: "max-height:" + (settings.height || 520) + "px" });
}

// --- heatmap -------------------------------------------------------------

export function heatmap(columns, rows, options) {
  const settings = options || {};
  const cell = settings.cell || 34;
  const labelWidth = settings.labelWidth || 190;
  const headerHeight = 58;
  const width = labelWidth + columns.length * cell + 40;
  const height = headerHeight + rows.length * cell;
  const max = Math.max(1, ...rows.flatMap((row) => row.cells));
  const parts = [];

  columns.forEach((column, c) => {
    const x = labelWidth + c * cell + cell / 2;
    parts.push('<text x="' + x + '" y="' + (headerHeight - 12)
      + '" font-size="10" fill="#6B6D76" text-anchor="start"'
      + ' transform="rotate(-45 ' + x + " " + (headerHeight - 12) + ')">'
      + esc(column) + "</text>");
  });

  rows.forEach((row, r) => {
    const y = headerHeight + r * cell;
    parts.push('<text x="0" y="' + (y + cell / 2 + 4) + '" font-size="11" fill="#1C1D21">'
      + esc(truncate(row.label, 28)) + "</text>");
    row.cells.forEach((value, c) => {
      const x = labelWidth + c * cell;
      const intensity = value / max;
      parts.push('<rect x="' + (x + 2) + '" y="' + (y + 2) + '" width="' + (cell - 4)
        + '" height="' + (cell - 4) + '" rx="2" fill="' + (row.color || "#2B4570")
        + '" fill-opacity="0"><animate attributeName="fill-opacity" from="0" to="'
        + (value ? (0.12 + intensity * 0.78).toFixed(3) : 0.04)
        + '" dur="0.6s" begin="' + ((r * 0.02) + (c * 0.015)).toFixed(2)
        + 's" fill="freeze"/><title>' + esc(row.label + " · " + columns[c] + ": " + value)
        + "</title></rect>");
      if (value) {
        parts.push('<text x="' + (x + cell / 2) + '" y="' + (y + cell / 2 + 4)
          + '" font-size="10" text-anchor="middle" fill="'
          + (intensity > 0.55 ? "#FAFAF7" : "#1C1D21") + '">' + value + "</text>");
      }
    });
  });
  return svg("0 0 " + width + " " + height, parts.join(""),
             { style: "min-width:" + Math.min(width, 900) + "px" });
}

// --- word cloud ----------------------------------------------------------

export function wordCloud(words, options) {
  const settings = options || {};
  const width = 720;
  const height = settings.height || 320;
  const top = words.slice(0, settings.limit || 60);
  if (!top.length) return h("div");
  const max = Math.max(...top.map((word) => word.weight || word.count || 1));
  const min = Math.min(...top.map((word) => word.weight || word.count || 1));
  const parts = [];
  const placed = [];
  const centre = { x: width / 2, y: height / 2 };

  top.forEach((word, i) => {
    const value = word.weight || word.count || 1;
    const scale = (value - min) / Math.max(1e-6, max - min);
    const size = 11 + scale * 30;
    const textWidth = String(word.term).length * size * 0.52;
    let angle = 0;
    let radius = 0;
    let x = centre.x;
    let y = centre.y;
    // spiral outwards until the word does not collide with an earlier one
    for (let step = 0; step < 900; step += 1) {
      x = centre.x + Math.cos(angle) * radius - textWidth / 2;
      y = centre.y + Math.sin(angle) * radius * 0.55;
      const box = { x, y: y - size, w: textWidth, h: size * 1.12 };
      const clash = placed.some((other) => !(box.x + box.w < other.x || other.x + other.w < box.x
        || box.y + box.h < other.y || other.y + other.h < box.y));
      const inside = box.x > 4 && box.x + box.w < width - 4 && box.y > 4
        && box.y + box.h < height - 4;
      if (!clash && inside) break;
      angle += 0.38;
      radius += 1.7;
    }
    placed.push({ x, y: y - size, w: textWidth, h: size * 1.12 });
    const opacity = 0.45 + scale * 0.55;
    parts.push('<text x="' + x.toFixed(1) + '" y="' + y.toFixed(1) + '" font-size="'
      + size.toFixed(1) + '" font-family="Georgia, serif" fill="'
      + (word.color || "#2B4570") + '" fill-opacity="0" style="cursor:default">'
      + '<animate attributeName="fill-opacity" from="0" to="' + opacity.toFixed(2)
      + '" dur="0.6s" begin="' + (i * 0.018).toFixed(2) + 's" fill="freeze"/>'
      + "<title>" + esc(word.term + " · " + (word.count || value) + " occurrences") + "</title>"
      + esc(word.term) + "</text>");
  });
  return svg("0 0 " + width + " " + height, parts.join(""));
}

// --- sparkline / arc -----------------------------------------------------

export function sparkline(values, options) {
  const settings = options || {};
  const width = settings.width || 320;
  const height = settings.height || 56;
  if (!values.length) return h("div");
  const max = Math.max(...values, 0.001);
  const min = Math.min(...values, -0.001);
  const range = Math.max(max - min, 0.001);
  const points = values.map((value, i) => {
    const x = (i / Math.max(values.length - 1, 1)) * (width - 4) + 2;
    const y = height - 4 - ((value - min) / range) * (height - 8);
    return (i ? "L" : "M") + x.toFixed(1) + " " + y.toFixed(1);
  }).join(" ");
  const zero = height - 4 - ((0 - min) / range) * (height - 8);
  const inner = '<line x1="0" y1="' + zero.toFixed(1) + '" x2="' + width + '" y2="'
    + zero.toFixed(1) + '" stroke="#E4E1D8"/>'
    + '<path d="' + points + '" fill="none" stroke="' + (settings.color || "#2B4570")
    + '" stroke-width="1.8" stroke-dasharray="1200" stroke-dashoffset="1200">'
    + '<animate attributeName="stroke-dashoffset" from="1200" to="0" dur="1.1s" fill="freeze"/>'
    + "</path>";
  return svg("0 0 " + width + " " + height, inner);
}

// --- stacked coverage bar -------------------------------------------------

export function stackedBar(segments, options) {
  const settings = options || {};
  const width = 640;
  const height = settings.height || 22;
  const total = segments.reduce((sum, segment) => sum + segment.value, 0) || 1;
  let x = 0;
  const parts = segments.map((segment, i) => {
    const w = (segment.value / total) * width;
    const rect = '<rect x="' + x.toFixed(1) + '" y="0" width="0" height="' + height
      + '" fill="' + segment.color + '" rx="2">'
      + '<animate attributeName="width" from="0" to="' + w.toFixed(1) + '" dur="0.7s"'
      + ' begin="' + (i * 0.08).toFixed(2) + 's" fill="freeze"/>'
      + "<title>" + esc(segment.label + ": " + segment.value) + "</title></rect>";
    x += w;
    return rect;
  }).join("");
  return svg("0 0 " + width + " " + height, parts, { style: "height:" + height + "px" });
}

// --- donut with legend ----------------------------------------------------

export function donutChart(segments, options) {
  const settings = options || {};
  const size = settings.size || 220;
  const centre = size / 2;
  const outer = centre - 8;
  const inner = outer - (settings.thickness || 30);
  const total = segments.reduce((sum, item) => sum + Math.max(item.value, 0), 0) || 1;
  let angle = -90;
  const parts = [];
  segments.forEach((segment, index) => {
    if (segment.value <= 0) return;
    const sweep = (360 * segment.value) / total;
    parts.push('<path d="' + arcPath(centre, centre, outer, inner, angle, angle + sweep)
      + '" fill="' + segment.color + '" fill-opacity="0"><animate attributeName="fill-opacity"'
      + ' from="0" to="0.92" dur="0.5s" begin="' + (index * 0.12).toFixed(2)
      + 's" fill="freeze"/><title>' + esc(segment.label + ": " + segment.value) + "</title></path>");
    angle += sweep;
  });
  if (settings.centre) {
    parts.push('<text x="' + centre + '" y="' + centre + '" text-anchor="middle" dy="6"'
      + ' font-size="30" font-family="Georgia, serif" fill="#1C1D21">'
      + esc(settings.centre) + "</text>");
  }
  if (settings.centreLabel) {
    parts.push('<text x="' + centre + '" y="' + (centre + 22) + '" text-anchor="middle"'
      + ' font-size="9" fill="#6B6D76">' + esc(settings.centreLabel) + "</text>");
  }
  return svg("0 0 " + size + " " + size, parts.join(""),
             { style: "max-width:" + size + "px" });
}

function arcPath(cx, cy, outer, inner, startDeg, endDeg) {
  const start = (startDeg * Math.PI) / 180;
  const end = (endDeg * Math.PI) / 180;
  const large = endDeg - startDeg > 180 ? 1 : 0;
  const x1 = cx + Math.cos(start) * outer;
  const y1 = cy + Math.sin(start) * outer;
  const x2 = cx + Math.cos(end) * outer;
  const y2 = cy + Math.sin(end) * outer;
  const x3 = cx + Math.cos(end) * inner;
  const y3 = cy + Math.sin(end) * inner;
  const x4 = cx + Math.cos(start) * inner;
  const y4 = cy + Math.sin(start) * inner;
  return "M" + x1.toFixed(2) + " " + y1.toFixed(2)
    + " A" + outer + " " + outer + " 0 " + large + " 1 " + x2.toFixed(2) + " " + y2.toFixed(2)
    + " L" + x3.toFixed(2) + " " + y3.toFixed(2)
    + " A" + inner + " " + inner + " 0 " + large + " 0 " + x4.toFixed(2) + " " + y4.toFixed(2)
    + " Z";
}

// --- grouped bars ---------------------------------------------------------

export function groupedBars(groups, series, options) {
  const settings = options || {};
  const width = settings.width || 640;
  const height = settings.height || 240;
  const padLeft = 34;
  const padBottom = 42;
  const plotHeight = height - padBottom - 14;
  const plotWidth = width - padLeft - 12;
  const max = Math.max(1, ...series.flatMap((entry) => entry.values));
  const parts = [];
  for (let step = 0; step <= 4; step += 1) {
    const y = 14 + plotHeight - (plotHeight * step) / 4;
    parts.push('<line x1="' + padLeft + '" y1="' + y + '" x2="' + (padLeft + plotWidth)
      + '" y2="' + y + '" stroke="#EDEBE4"/>');
    parts.push('<text x="' + (padLeft - 6) + '" y="' + (y + 3)
      + '" font-size="9" fill="#6B6D76" text-anchor="end">'
      + Math.round((max * step) / 4) + "</text>");
  }
  const groupWidth = plotWidth / Math.max(groups.length, 1);
  const barWidth = (groupWidth - 12) / Math.max(series.length, 1);
  groups.forEach((group, index) => {
    const base = padLeft + index * groupWidth;
    series.forEach((entry, seriesIndex) => {
      const value = entry.values[index] || 0;
      const barHeight = (value / max) * plotHeight;
      const x = base + 6 + seriesIndex * barWidth;
      const y = 14 + plotHeight - barHeight;
      parts.push('<rect x="' + x.toFixed(1) + '" y="' + (14 + plotHeight)
        + '" width="' + (barWidth - 3).toFixed(1) + '" height="0" rx="2" fill="'
        + entry.color + '"><animate attributeName="height" from="0" to="'
        + barHeight.toFixed(1) + '" dur="0.7s" begin="' + (index * 0.06).toFixed(2)
        + 's" fill="freeze"/><animate attributeName="y" from="' + (14 + plotHeight)
        + '" to="' + y.toFixed(1) + '" dur="0.7s" begin="' + (index * 0.06).toFixed(2)
        + 's" fill="freeze"/><title>' + esc(entry.name + " " + group + ": " + value)
        + "</title></rect>");
      if (value) {
        parts.push('<text x="' + (x + (barWidth - 3) / 2).toFixed(1) + '" y="'
          + (y - 4).toFixed(1) + '" font-size="9" fill="#6B6D76" text-anchor="middle">'
          + value + "</text>");
      }
    });
    parts.push('<text x="' + (base + groupWidth / 2).toFixed(1) + '" y="'
      + (height - 22) + '" font-size="10" fill="#6B6D76" text-anchor="middle">'
      + esc(group) + "</text>");
  });
  let legendX = padLeft;
  series.forEach((entry) => {
    parts.push('<rect x="' + legendX + '" y="' + (height - 12) + '" width="9" height="9"'
      + ' rx="2" fill="' + entry.color + '"/>');
    parts.push('<text x="' + (legendX + 14) + '" y="' + (height - 4)
      + '" font-size="10" fill="#1C1D21">' + esc(entry.name) + "</text>");
    legendX += 30 + entry.name.length * 6;
  });
  return svg("0 0 " + width + " " + height, parts.join(""));
}

// --- radar ----------------------------------------------------------------

export function radarChart(axes, series, options) {
  const settings = options || {};
  const size = settings.size || 460;
  const centre = size / 2;
  const radius = centre - (settings.margin || 96);
  const maximum = settings.max || 10;
  const count = Math.max(axes.length, 3);
  const angles = [];
  for (let index = 0; index < count; index += 1) {
    angles.push(-Math.PI / 2 + (2 * Math.PI * index) / count);
  }
  const parts = [];
  for (let ring = 1; ring <= 5; ring += 1) {
    const r = (radius * ring) / 5;
    const points = angles.map((angle) =>
      (centre + Math.cos(angle) * r).toFixed(1) + "," + (centre + Math.sin(angle) * r).toFixed(1));
    parts.push('<polygon points="' + points.join(" ") + '" fill="none" stroke="#E4E1D8"/>');
  }
  angles.forEach((angle) => {
    parts.push('<line x1="' + centre + '" y1="' + centre + '" x2="'
      + (centre + Math.cos(angle) * radius).toFixed(1) + '" y2="'
      + (centre + Math.sin(angle) * radius).toFixed(1) + '" stroke="#E4E1D8"/>');
  });
  series.forEach((entry, seriesIndex) => {
    const points = angles.map((angle, index) => {
      const value = entry.values[index] || 0;
      const r = radius * Math.max(0, Math.min(1, value / maximum));
      return (centre + Math.cos(angle) * r).toFixed(1) + ","
        + (centre + Math.sin(angle) * r).toFixed(1);
    });
    parts.push('<polygon points="' + points.join(" ") + '" fill="' + entry.color
      + '" fill-opacity="0.10" stroke="' + entry.color + '" stroke-width="2"'
      + ' opacity="0"><animate attributeName="opacity" from="0" to="1" dur="0.6s" begin="'
      + (seriesIndex * 0.2).toFixed(2) + 's" fill="freeze"/></polygon>');
    points.forEach((point) => {
      const [x, y] = point.split(",");
      parts.push('<circle cx="' + x + '" cy="' + y + '" r="3" fill="' + entry.color + '"/>');
    });
  });
  axes.forEach((axis, index) => {
    const angle = angles[index];
    const x = centre + Math.cos(angle) * (radius + 16);
    const y = centre + Math.sin(angle) * (radius + 16);
    const anchor = Math.cos(angle) > 0.25 ? "start"
      : Math.cos(angle) < -0.25 ? "end" : "middle";
    const words = String(axis).split(" ");
    const lines = [];
    let current = "";
    for (const word of words) {
      if ((current + " " + word).trim().length > 16) {
        lines.push(current.trim());
        current = word;
      } else {
        current = (current + " " + word).trim();
      }
    }
    if (current) lines.push(current);
    lines.forEach((line, lineIndex) => {
      parts.push('<text x="' + x.toFixed(1) + '" y="' + (y + lineIndex * 11).toFixed(1)
        + '" font-size="10" fill="#1C1D21" text-anchor="' + anchor + '">'
        + esc(line) + "</text>");
    });
  });
  let legendX = 8;
  series.forEach((entry) => {
    parts.push('<rect x="' + legendX + '" y="' + (size - 14) + '" width="9" height="9"'
      + ' rx="2" fill="' + entry.color + '"/>');
    parts.push('<text x="' + (legendX + 14) + '" y="' + (size - 6)
      + '" font-size="10" fill="#1C1D21">' + esc(entry.name) + "</text>");
    legendX += 30 + entry.name.length * 6;
  });
  return svg("0 0 " + size + " " + size, parts.join(""),
             { style: "max-height:" + (settings.height || size) + "px" });
}

// --- scroll reveal --------------------------------------------------------

export function observeReveals(root, attempt) {
  const scope = root || document;
  const nodes = Array.from(scope.querySelectorAll(".reveal"));
  if (!nodes.length) return;
  // Called before the view is attached, geometry is all zeros and nothing would
  // ever reveal; wait for the node to land in the document first.
  if (!nodes[0].isConnected && (attempt || 0) < 20) {
    setTimeout(() => observeReveals(root, (attempt || 0) + 1), 30);
    return;
  }

  // A geometry check runs alongside the observer. IntersectionObserver is
  // throttled in background tabs and absent in older engines; content must
  // never be left invisible because an animation hook did not fire.
  function sweep() {
    const height = window.innerHeight || document.documentElement.clientHeight || 800;
    for (const node of nodes) {
      if (node.classList.contains("is-in")) continue;
      const box = node.getBoundingClientRect();
      if (box.top < height - 40 && box.bottom > 0) node.classList.add("is-in");
    }
  }

  let scheduled = false;
  function onScroll() {
    if (scheduled) return;
    scheduled = true;
    // a timer, not requestAnimationFrame: frames stop in a hidden tab and the
    // sweep would then never run
    setTimeout(() => {
      scheduled = false;
      if (!document.body.contains(nodes[0])) {
        window.removeEventListener("scroll", onScroll);
        window.removeEventListener("resize", onScroll);
        return;
      }
      sweep();
    }, 24);
  }

  if (typeof IntersectionObserver === "function") {
    const observer = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-in");
          observer.unobserve(entry.target);
        }
      }
    }, { threshold: 0.12, rootMargin: "0px 0px -40px 0px" });
    nodes.forEach((node) => observer.observe(node));
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", onScroll);
  document.addEventListener("visibilitychange", sweep);
  sweep();
  setTimeout(sweep, 400);
}
