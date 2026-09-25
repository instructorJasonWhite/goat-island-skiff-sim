(function (root, factory) {
  const api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root) root.GISMapView = api;
})(typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';

  // World coordinates are metres, +x east and +y north. The map stays north-up.
  function createProjector(map, width, height) {
    const ring = map.water_polygon;
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const point of ring) {
      if (point[0] < minX) minX = point[0];
      if (point[0] > maxX) maxX = point[0];
      if (point[1] < minY) minY = point[1];
      if (point[1] > maxY) maxY = point[1];
    }
    const margin = height * .08;
    const fit = Math.min((width - 2 * margin) / Math.max(1, maxX - minX),
      (height - 2 * margin) / Math.max(1, maxY - minY));
    const midX = (minX + maxX) / 2, midY = (minY + maxY) / 2;
    return (x, y) => ({ x: width / 2 + (x - midX) * fit,
      y: height / 2 - (y - midY) * fit });
  }

  function traceRing(ctx, ring, project) {
    ctx.beginPath();
    ring.forEach((point, i) => {
      const p = project(point[0], point[1]);
      if (i) ctx.lineTo(p.x, p.y);
      else ctx.moveTo(p.x, p.y);
    });
    ctx.closePath();
  }

  function makeCanvas(canvas, width, height) {
    const doc = canvas.ownerDocument || (typeof document !== 'undefined' ? document : null);
    const base = doc ? doc.createElement('canvas') : new OffscreenCanvas(width, height);
    base.width = width;
    base.height = height;
    return base;
  }

  function drawBase(base, map, project, large) {
    const ctx = base.getContext('2d');
    const w = base.width, h = base.height;
    ctx.fillStyle = '#1e403e';
    ctx.fillRect(0, 0, w, h);
    traceRing(ctx, map.water_polygon, project);
    ctx.fillStyle = '#55abb0';
    ctx.fill();
    // Narrow coves can be one pixel wide at full-lake scale; retain their water fill.
    ctx.lineWidth = large ? .8 : .4;
    ctx.strokeStyle = '#e3d59b';
    ctx.stroke();
    for (const island of map.islands || []) {
      traceRing(ctx, island, project);
      ctx.fillStyle = '#225044';
      ctx.fill();
      if (large) {
        ctx.strokeStyle = '#c8c78e';
        ctx.lineWidth = 1.2;
        ctx.stroke();
      }
    }
  }

  function drawMarks(ctx, project, marks, activeMark, large, width, height) {
    const items = marks || [];
    items.forEach((mark, index) => {
      const p = project(mark.x, mark.y), active = index === activeMark;
      const radius = large ? (active ? 7 : 6) : (active ? 4 : 3);
      ctx.beginPath();
      ctx.arc(p.x, p.y, radius + (large ? 2 : 1), 0, Math.PI * 2);
      ctx.fillStyle = '#102e31';
      ctx.fill();
      ctx.beginPath();
      ctx.arc(p.x, p.y, radius, 0, Math.PI * 2);
      ctx.fillStyle = mark.color || '#f0cc85';
      ctx.fill();
      if (large) {
        ctx.font = '800 9px Segoe UI, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillStyle = '#143336';
        ctx.fillText(String(index + 1), p.x, p.y + .5);
      }
    });
    if (!large || !items.length) return;
    // A fixed legend remains readable when nearby buoys overlap on a full-lake map.
    ctx.fillStyle = 'rgba(8,34,39,.9)';
    ctx.fillRect(0, height - 33, width, 33);
    ctx.font = '700 12px Segoe UI, sans-serif';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    const cell = width / items.length;
    items.forEach((mark, index) => {
      const x = index * cell + 15;
      ctx.fillStyle = mark.color || '#f0cc85';
      ctx.beginPath(); ctx.arc(x, height - 16, 5, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = index === activeMark ? '#fff3c8' : '#d6e9dd';
      ctx.fillText(`${index + 1}  ${mark.name || 'Course mark'}`, x + 12, height - 16);
    });
  }

  function drawNorth(ctx, width) {
    ctx.save();
    ctx.fillStyle = 'rgba(7,33,38,.9)';
    ctx.fillRect(width - 49, 8, 40, 43);
    ctx.fillStyle = '#f7e6b4';
    ctx.font = '800 14px Segoe UI, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('N', width - 29, 18);
    ctx.beginPath();
    ctx.moveTo(width - 29, 25);
    ctx.lineTo(width - 35, 42);
    ctx.lineTo(width - 29, 38);
    ctx.lineTo(width - 23, 42);
    ctx.closePath();
    ctx.fill();
    ctx.restore();
  }

  function drawBoat(ctx, project, boat, large, width, height) {
    if (!boat || !Number.isFinite(boat.x) || !Number.isFinite(boat.y)) return;
    const p = project(boat.x, boat.y), radius = large ? 12 : 6;
    ctx.save();
    ctx.beginPath(); ctx.arc(p.x, p.y, radius * 1.45, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(255,246,179,.3)'; ctx.fill();
    ctx.lineWidth = large ? 2.4 : 1.4;
    ctx.strokeStyle = '#17363c'; ctx.stroke();
    ctx.translate(p.x, p.y);
    ctx.rotate(Number.isFinite(boat.heading) ? boat.heading : 0);
    ctx.beginPath();
    ctx.moveTo(0, -radius);
    ctx.lineTo(radius * .72, radius * .75);
    ctx.lineTo(0, radius * .38);
    ctx.lineTo(-radius * .72, radius * .75);
    ctx.closePath();
    ctx.fillStyle = '#fff8d3'; ctx.fill();
    ctx.lineWidth = large ? 2.5 : 1.4;
    ctx.strokeStyle = '#0c303a'; ctx.stroke();
    ctx.restore();
    if (!large) return;
    const labelWidth = 125;
    const labelX = Math.max(5, Math.min(width - labelWidth - 5,
      p.x + (p.x > width * .7 ? -labelWidth - 19 : 19)));
    const labelY = Math.max(5, Math.min(height - 57,
      p.y < 43 ? p.y + 17 : p.y - 34));
    ctx.fillStyle = '#fff0af';
    ctx.fillRect(labelX, labelY, labelWidth, 25);
    ctx.fillStyle = '#16373a';
    ctx.font = '800 11px Segoe UI, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('YOU ARE HERE', labelX + labelWidth / 2, labelY + 13);
  }

  function createPainter(canvas, options = {}) {
    const ctx = canvas.getContext('2d');
    const large = !!options.large;
    let cachedMap = null, cachedWidth = 0, cachedHeight = 0;
    let base = null, project = null;
    return { draw(map, boat, marks, activeMark) {
      if (!map || !Array.isArray(map.water_polygon) || map.water_polygon.length < 3) return;
      const width = canvas.width, height = canvas.height;
      if (map !== cachedMap || width !== cachedWidth || height !== cachedHeight) {
        project = createProjector(map, width, height);
        base = makeCanvas(canvas, width, height);
        drawBase(base, map, project, large);
        cachedMap = map; cachedWidth = width; cachedHeight = height;
      }
      ctx.drawImage(base, 0, 0);
      drawMarks(ctx, project, marks, activeMark, large, width, height);
      if (large) drawNorth(ctx, width);
      drawBoat(ctx, project, boat, large, width, height);
    } };
  }

  return { createProjector, createPainter };
});
