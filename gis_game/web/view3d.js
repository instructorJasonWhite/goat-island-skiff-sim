/* Canvas perspective view for the sailing prototype. No external renderer required.
 * Coordinates are metres: +x east, +y north; heading is clockwise from north.
 * The camera stays with the boat, while water, shoreline, marks and wake stay
 * in world coordinates, making even small changes in speed visible.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.GISView3D = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const TAU = Math.PI * 2;
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const hash = (a, b) => {
    const n = Math.sin(a * 127.1 + b * 311.7) * 43758.5453;
    return n - Math.floor(n);
  };
  const shorelineCache = new WeakMap();

  // Screen rendering may drop sub-metre bends, while collision and minimap
  // continue to use the untouched source polygon. Cache the result per map.
  function simplifyRing(ring, tolerance = 3) {
    if (!ring || ring.length < 16) return ring || [];
    const n = ring.length;
    let split = 1, far = -1;
    for (let i = 1; i < n; i++) {
      const dx = ring[i][0] - ring[0][0], dy = ring[i][1] - ring[0][1];
      const d2 = dx * dx + dy * dy;
      if (d2 > far) { far = d2; split = i; }
    }
    if (split === n - 1) split = Math.floor(n / 2);
    const keep = new Uint8Array(n); keep[0] = 1; keep[split] = 1;
    const tolerance2 = tolerance * tolerance;
    function simplifyOpen(start, end, wrapEnd) {
      const stack = [[start, end, wrapEnd]];
      while (stack.length) {
        const [a, b, wrap] = stack.pop();
        const A = ring[a], B = ring[b % n];
        const ux = B[0] - A[0], uy = B[1] - A[1];
        const den = ux * ux + uy * uy || 1;
        let best = -1, maxD2 = tolerance2;
        for (let j = a + 1; j < b; j++) {
          const P = ring[j % n];
          const t = clamp(((P[0]-A[0])*ux + (P[1]-A[1])*uy) / den, 0, 1);
          const dx = P[0] - A[0] - t * ux, dy = P[1] - A[1] - t * uy;
          const d2 = dx * dx + dy * dy;
          if (d2 > maxD2) { maxD2 = d2; best = j; }
        }
        if (best >= 0) {
          keep[best % n] = 1;
          stack.push([a, best, wrap], [best, b, wrap]);
        }
      }
    }
    simplifyOpen(0, split, false);
    simplifyOpen(split, n, true);
    const out = [];
    for (let i = 0; i < n; i++) if (keep[i]) out.push(ring[i]);
    return out.length >= 3 ? out : ring;
  }

  function shorelineFor(map) {
    let cached = shorelineCache.get(map);
    if (!cached || cached.source !== map.water_polygon || cached.islandsSource !== map.islands) {
      cached = { source: map.water_polygon, islandsSource: map.islands,
        water: simplifyRing(map.water_polygon),
        islands: (map.islands || []).map(ring => simplifyRing(ring, 2)),
        waterIndex: buildEdgeIndex([map.water_polygon]),
        islandIndex: buildEdgeIndex(map.islands || []),
        groundEdges: listEdges([map.water_polygon, ...(map.islands || [])]),
        displayEdges: listEdges([simplifyRing(map.water_polygon),
          ...(map.islands || []).map(ring => simplifyRing(ring, 2))]),
        groundNearby: null, displayNearby: null };
      shorelineCache.set(map, cached);
    }
    return cached;
  }

  function listEdges(rings) {
    const out = [];
    for (const ring of rings) for (let i = 0; i < ring.length; i++) {
      const a = ring[i], b = ring[(i + 1) % ring.length];
      const dx = b[0] - a[0], dy = b[1] - a[1];
      const halfLength = Math.hypot(dx, dy) * .5;
      out.push([a[0], a[1], b[0], b[1], (a[0] + b[0]) * .5,
        (a[1] + b[1]) * .5, halfLength, i]);
    }
    return out;
  }

  function nearbyEdges(shoreline, cam, kind) {
    const ground = kind === 'ground';
    const name = ground ? 'groundNearby' : 'displayNearby';
    const radius = ground ? 6000 : 720;
    const old = shoreline[name];
    if (old && Math.hypot(cam.x - old.x, cam.y - old.y) < 90) return old.edges;
    const source = ground ? shoreline.groundEdges : shoreline.displayEdges;
    const selected = [];
    for (const edge of source) {
      const reach = radius + edge[6];
      const dx = edge[4] - cam.x, dy = edge[5] - cam.y;
      if (dx * dx + dy * dy <= reach * reach) selected.push(edge);
    }
    shoreline[name] = { x: cam.x, y: cam.y, edges: selected };
    return selected;
  }

  function buildEdgeIndex(rings) {
    const buckets = new Map(), cell = 70;
    for (const ring of rings) for (let i = 0; i < ring.length; i++) {
      const a = ring[i], b = ring[(i + 1) % ring.length];
      if (a[1] === b[1]) continue;
      const edge = [a[0], a[1], b[0], b[1]];
      const lo = Math.floor(Math.min(a[1], b[1]) / cell);
      const hi = Math.floor(Math.max(a[1], b[1]) / cell);
      for (let k = lo; k <= hi; k++) {
        let bucket = buckets.get(k);
        if (!bucket) { bucket = []; buckets.set(k, bucket); }
        bucket.push(edge);
      }
    }
    return { buckets, cell };
  }

  function insideIndexed(index, x, y) {
    const edges = index.buckets.get(Math.floor(y / index.cell));
    if (!edges) return false;
    let inside = false;
    for (const e of edges) {
      if ((e[1] > y) !== (e[3] > y) &&
          x < (e[2]-e[0]) * (y-e[1]) / (e[3]-e[1]) + e[0]) inside = !inside;
    }
    return inside;
  }

  function isWater(shoreline, x, y) {
    return insideIndexed(shoreline.waterIndex, x, y) &&
      !insideIndexed(shoreline.islandIndex, x, y);
  }

  function screenToGround(cam, x, y) {
    let sx = (x - cam.width * .5) / cam.focal;
    let sy = (y - cam.height * .5) / cam.focal;
    const cr = cam.cr, sr = cam.sr;
    const unrolledX = sx * cr + sy * sr;
    const unrolledY = -sx * sr + sy * cr;
    const sp = cam.sp, cp = cam.cp;
    const denominator = sp + unrolledY * cp;
    if (denominator <= .0001) return null;
    const depth = cam.z / denominator;
    const side = unrolledX * depth;
    const forward = depth * (cp - unrolledY * sp);
    return { x: cam.x + cam.r.x * side + cam.f.x * forward,
      y: cam.y + cam.r.y * side + cam.f.y * forward, depth };
  }

  function horizonY(cam, x) {
    return cam.height * .5 + (x - cam.width * .5) * cam.sr / cam.cr -
      cam.focal * cam.sp / (cam.cp * cam.cr);
  }

  function groundInterval(cam, y) {
    const left = horizonY(cam, 0), right = horizonY(cam, cam.width);
    if (y <= Math.min(left, right)) return null;
    if (y >= Math.max(left, right)) return [0, cam.width];
    const cross = clamp(cam.width * (y - left) / (right - left), 0, cam.width);
    return right > left ? [0, cross] : [cross, cam.width];
  }

  function makeCamera(boat, width, height, mode) {
    const first = mode === 'first';
    const heading = Number.isFinite(boat.heading) ? boat.heading : 0;
    const f = { x: Math.sin(heading), y: Math.cos(heading) };
    const r = { x: Math.cos(heading), y: -Math.sin(heading) };
    const side = first ? 0.12 : 0.95;
    const ahead = first ? -1.55 : -6.55;
    const z = first ? 1.52 : 2.62;
    const pitch = first ? 0.055 : 0.095;
    const roll = -(boat.heel || 0) * (first ? 0.58 : 0.10);
    return {
      x: boat.x + side * r.x + ahead * f.x,
      y: boat.y + side * r.y + ahead * f.y,
      z,
      f, r, pitch, roll,
      sp: Math.sin(pitch), cp: Math.cos(pitch), sr: Math.sin(roll), cr: Math.cos(roll),
      width, height,
      focal: first ? Math.min(width * .94, height * 1.25) : Math.min(width * .91, height * 1.12),
      near: 0.32,
      mode: first ? 'first' : 'chase'
    };
  }

  function toCamera(cam, x, y, z) {
    const dx = x - cam.x, dy = y - cam.y;
    return { side: dx * cam.r.x + dy * cam.r.y,
      forward: dx * cam.f.x + dy * cam.f.y, vertical: z - cam.z };
  }

  function cameraDepth(cam, p) {
    return p.forward * cam.cp - p.vertical * cam.sp;
  }

  function projectCamera(cam, p) {
    const depth = cameraDepth(cam, p);
    if (depth < cam.near - 1e-8 || !Number.isFinite(depth)) return { visible: false, depth };
    const up = p.forward * cam.sp + p.vertical * cam.cp;
    const sx = cam.focal * p.side / depth;
    const sy = -cam.focal * up / depth;
    const cr = cam.cr, sr = cam.sr;
    return {
      x: cam.width * 0.5 + clamp(sx * cr - sy * sr, -cam.width * 8, cam.width * 8),
      y: cam.height * 0.5 + clamp(sx * sr + sy * cr, -cam.height * 8, cam.height * 8),
      depth, visible: true
    };
  }

  function projectWorld(cam, x, y, z = 0) {
    return projectCamera(cam, toCamera(cam, x, y, z));
  }

  function clipNear(cam, points) {
    if (!points || points.length < 2) return [];
    const out = [];
    let last = points[points.length - 1], lastD = cameraDepth(cam, last);
    for (const p of points) {
      const d = cameraDepth(cam, p), lastInside = lastD >= cam.near, inside = d >= cam.near;
      if (lastInside !== inside) {
        const t = (cam.near - lastD) / (d - lastD);
        out.push({ side: last.side + (p.side - last.side) * t,
          forward: last.forward + (p.forward - last.forward) * t,
          vertical: last.vertical + (p.vertical - last.vertical) * t });
      }
      if (inside) out.push(p);
      last = p; lastD = d;
    }
    return out;
  }

  function projectedPolygon(ctx, cam, points) {
    const clipped = clipNear(cam, points);
    if (clipped.length < 3) return false;
    ctx.beginPath();
    clipped.forEach((p, i) => {
      const q = projectCamera(cam, p);
      if (i) ctx.lineTo(q.x, q.y); else ctx.moveTo(q.x, q.y);
    });
    ctx.closePath();
    return true;
  }

  function drawPoly(ctx, cam, points, fill, stroke, lineWidth) {
    if (!projectedPolygon(ctx, cam, points)) return;
    if (fill) { ctx.fillStyle = fill; ctx.fill(); }
    if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = lineWidth || 1; ctx.stroke(); }
  }

  function drawLine(ctx, cam, a, b, color, width) {
    let d0 = cameraDepth(cam, a), d1 = cameraDepth(cam, b);
    if (d0 < cam.near && d1 < cam.near) return;
    if (d0 < cam.near || d1 < cam.near) {
      const t = (cam.near - d0) / (d1 - d0);
      const cut = { side: a.side + (b.side - a.side) * t,
        forward: a.forward + (b.forward - a.forward) * t,
        vertical: a.vertical + (b.vertical - a.vertical) * t };
      if (d0 < cam.near) { a = cut; d0 = cam.near; }
      else { b = cut; d1 = cam.near; }
    }
    const p = projectCamera(cam, a), q = projectCamera(cam, b);
    if (!p.visible || !q.visible) return;
    ctx.strokeStyle = color; ctx.lineWidth = width;
    ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(q.x, q.y); ctx.stroke();
  }

  function pointInPolygon(x, y, poly) {
    if (!poly || poly.length < 3) return false;
    let inside = false;
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      const a = poly[i], b = poly[j];
      if ((a[1] > y) !== (b[1] > y) &&
          x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]) inside = !inside;
    }
    return inside;
  }

  function drawBackground(ctx, cam, time) {
    const w = cam.width, h = cam.height;
    const sky = ctx.createLinearGradient(0, 0, 0, h);
    sky.addColorStop(0, '#8eb5ce'); sky.addColorStop(0.48, '#b4d0d9');
    sky.addColorStop(0.70, '#d8d5bd'); sky.addColorStop(1, '#bac8bb');
    ctx.fillStyle = sky; ctx.fillRect(0, 0, w, h);
    const leftH = horizonY(cam, 0), rightH = horizonY(cam, w);
    // Light clouds and a far tree line give the eye a fixed horizon.
    ctx.fillStyle = 'rgba(255,255,246,.18)';
    for (let i = 0; i < 5; i++) {
      const cx = ((i * 0.26 + 0.13) * w + time * (1 + i % 2)) % (w + 220) - 110;
      const cy = h * (0.10 + (i % 3) * 0.055);
      ctx.beginPath(); ctx.ellipse(cx, cy, 85 + i * 8, 12 + (i % 3) * 3, 0, 0, TAU); ctx.fill();
    }
    ctx.fillStyle = '#466c63';
    ctx.beginPath(); ctx.moveTo(0,leftH-2); ctx.lineTo(w,rightH-2);
    ctx.lineTo(w,h); ctx.lineTo(0,h); ctx.closePath(); ctx.fill();
    const land = ctx.createLinearGradient(0, Math.min(leftH,rightH), 0, h);
    land.addColorStop(0, '#668268'); land.addColorStop(0.22, '#3f674e');
    land.addColorStop(1, '#203d3a');
    ctx.fillStyle = land;
    ctx.beginPath(); ctx.moveTo(0,leftH+5); ctx.lineTo(w,rightH+5);
    ctx.lineTo(w,h); ctx.lineTo(0,h); ctx.closePath(); ctx.fill();
  }

  function drawWater(ctx, cam, shoreline, boat, time) {
    // Project source shoreline segments into screen rows. A single sample at
    // the left of each row establishes the water/land parity; every crossing
    // then flips it. This uses the original USGS edges at near shore and does
    // not perform thousands of point-in-polygon queries per frame.
    const yStep = 3;
    const centerHorizon = horizonY(cam, cam.width*.5);
    const firstY = Math.max(0, Math.floor(Math.min(horizonY(cam,0), horizonY(cam,cam.width)) / yStep) * yStep);
    const rowCount = Math.ceil((cam.height - firstY) / yStep);
    const rows = Array.from({ length: rowCount }, () => []);
    for (const edge of nearbyEdges(shoreline, cam, 'ground')) {
      let a = toCamera(cam, edge[0], edge[1], 0);
      let b = toCamera(cam, edge[2], edge[3], 0);
      const da = cameraDepth(cam, a), db = cameraDepth(cam, b);
      if (da < cam.near && db < cam.near) continue;
      if (da < cam.near || db < cam.near) {
        const t = (cam.near - da) / (db - da);
        const cut = { side: a.side + (b.side-a.side)*t,
          forward: a.forward + (b.forward-a.forward)*t,
          vertical: a.vertical + (b.vertical-a.vertical)*t };
        if (da < cam.near) a = cut; else b = cut;
      }
      const p = projectCamera(cam, a), q = projectCamera(cam, b);
      if (!p.visible || !q.visible || (p.x < 0 && q.x < 0) ||
          (p.x > cam.width && q.x > cam.width)) continue;
      const low = Math.max(0, Math.ceil((Math.min(p.y,q.y) - firstY - yStep*.5) / yStep));
      const high = Math.min(rowCount-1, Math.floor((Math.max(p.y,q.y) - firstY - yStep*.5) / yStep));
      if (low > high || p.y === q.y) continue;
      for (let j = low; j <= high; j++) {
        const yy = firstY + j*yStep + yStep*.5;
        if ((p.y > yy) === (q.y > yy)) continue;
        const x = p.x + (q.x-p.x) * (yy-p.y) / (q.y-p.y);
        if (x > 0 && x < cam.width) rows[j].push(x);
      }
    }
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(0,horizonY(cam,0));
    ctx.lineTo(cam.width,horizonY(cam,cam.width));
    ctx.lineTo(cam.width,cam.height);
    ctx.lineTo(0,cam.height);
    ctx.closePath();
    ctx.clip();
    for (let j = 0; j < rowCount; j++) {
      const y = firstY + j*yStep;
      const sampleY = y + yStep * .5;
      const ground = groundInterval(cam, sampleY);
      if (!ground || ground[1] - ground[0] < .5) continue;
      const t = clamp((sampleY - centerHorizon) / Math.max(1, cam.height - centerHorizon), 0, 1);
      const red = Math.round(71 - 53 * t), green = Math.round(126 - 69 * t), blue = Math.round(137 - 62 * t);
      ctx.fillStyle = `rgb(${red},${green},${blue})`;
      const origin = screenToGround(cam, ground[0]+.25, sampleY);
      let water = origin !== null && isWater(shoreline, origin.x, origin.y);
      let runStart = 0;
      const crossings = rows[j];
      crossings.sort((a,b)=>a-b);
      for (const x of crossings) {
        if (x <= ground[0] || x >= ground[1]) continue;
        if (water) ctx.fillRect(runStart, y, x-runStart, yStep+.5);
        water = !water; runStart = x;
      }
      if (water) ctx.fillRect(runStart, y, cam.width-runStart, yStep+.5);
    }
    ctx.restore();
    const wx0 = Math.floor((boat.x - 210) / 13), wx1 = Math.ceil((boat.x + 210) / 13);
    const wy0 = Math.floor((boat.y - 210) / 13), wy1 = Math.ceil((boat.y + 210) / 13);
    for (let ix = wx0; ix <= wx1; ix++) for (let iy = wy0; iy <= wy1; iy++) {
      if (hash(ix, iy) < .26) continue;
      const x = ix * 13 + hash(iy, ix) * 9;
      const y = iy * 13 + hash(ix + 19, iy) * 9;
      const q = projectWorld(cam, x, y, 0.05 + .02 * Math.sin(time * 2.4 + ix));
      if (!q.visible || q.depth > 210 || q.x < -20 || q.x > cam.width + 20 || q.y < 0 || q.y > cam.height + 12) continue;
      if (!isWater(shoreline, x, y)) continue;
      const len = clamp(50 / q.depth, 1.1, 12) * (.5 + hash(ix, iy + 5));
      const fade = clamp(1 - q.depth / 250, 0, .7);
      ctx.strokeStyle = `rgba(216,239,227,${(.12 + .26 * hash(ix + 4, iy)) * fade})`;
      ctx.lineWidth = clamp(20 / q.depth, .55, 2);
      ctx.beginPath(); ctx.moveTo(q.x - len, q.y); ctx.quadraticCurveTo(q.x, q.y - 1.5, q.x + len, q.y); ctx.stroke();
    }
  }

  function drawTree(ctx, cam, x, y, seed, depth) {
    const crownHeight = 6 + hash(seed, 13) * 5;
    const base = projectWorld(cam, x, y, .15), top = projectWorld(cam, x, y, crownHeight);
    if (!base.visible || !top.visible || base.x < -100 || base.x > cam.width + 100 || top.y > cam.height || depth > 600) return;
    const crown = clamp(cam.focal * (3.8 + hash(seed, 17) * 2.8) / depth, 1.4, 80);
    ctx.strokeStyle = '#354d3b'; ctx.lineWidth = Math.max(1, crown * .13);
    ctx.beginPath(); ctx.moveTo(base.x, base.y); ctx.lineTo(top.x, top.y + crown * .7); ctx.stroke();
    ctx.fillStyle = hash(seed, 3) > .5 ? '#214d3f' : '#365c42';
    ctx.beginPath(); ctx.moveTo(top.x, top.y - crown * .3);
    ctx.lineTo(top.x - crown * .8, top.y + crown * 1.7);
    ctx.quadraticCurveTo(top.x, top.y + crown * 1.15, top.x + crown * .85, top.y + crown * 1.7);
    ctx.closePath(); ctx.fill();
    ctx.fillStyle = 'rgba(111,143,87,.18)';
    ctx.beginPath(); ctx.moveTo(top.x, top.y); ctx.lineTo(top.x - crown * .52, top.y + crown * 1.25);
    ctx.lineTo(top.x, top.y + crown * .85); ctx.closePath(); ctx.fill();
  }

  function drawShore(ctx, cam, shoreline) {
    const trees = [];
    for (const edge of nearbyEdges(shoreline, cam, 'display')) {
      const i = edge[7];
      const a = toCamera(cam, edge[0], edge[1], 0.06);
      const b = toCamera(cam, edge[2], edge[3], 0.06);
      const light = i % 3 === 0 ? 'rgba(192,181,127,.86)' : 'rgba(160,174,124,.72)';
      const d = Math.max(2, (cameraDepth(cam, a) + cameraDepth(cam, b)) * .5);
      drawLine(ctx, cam, a, b, 'rgba(27,60,55,.55)', clamp(360 / d, 1, 13));
      drawLine(ctx, cam, a, b, light, clamp(90 / d, .7, 3.2));
      const n = Math.min(45, Math.floor(edge[6] * 2 / 25));
      for (let k = 0; k <= n; k++) {
        const t = (k + .4 * hash(i, k)) / Math.max(1, n + 1);
        const x = edge[0] + (edge[2] - edge[0]) * t;
        const y = edge[1] + (edge[3] - edge[1]) * t;
        const dist = Math.hypot(x - cam.x, y - cam.y);
        if (dist < 520 && dist > 12 && hash(i + k * 7, Math.floor(x + y)) > .22)
          trees.push({ x, y, dist, seed: i * 1009 + k * 37 });
      }
    }
    trees.sort((a, b) => b.dist - a.dist);
    for (const tree of trees) drawTree(ctx, cam, tree.x, tree.y, tree.seed, tree.dist);
  }

  function drawCourse(ctx, cam, marks, activeMark, time) {
    const items = (marks || []).map((m, i) => ({ ...m, index: i, depth: projectWorld(cam, m.x, m.y, 0).depth }))
      .filter(m => m.depth > cam.near && m.depth < 900).sort((a, b) => b.depth - a.depth);
    for (const m of items) {
      const base = projectWorld(cam, m.x, m.y, .1), top = projectWorld(cam, m.x, m.y, 1.35);
      if (!base.visible || !top.visible || base.x < -80 || base.x > cam.width + 80) continue;
      const r = clamp(cam.focal * .45 / base.depth, 2, 28);
      ctx.fillStyle = 'rgba(9,40,53,.28)';
      ctx.beginPath(); ctx.ellipse(base.x, base.y + r * .3, r * 1.5, r * .37, 0, 0, TAU); ctx.fill();
      ctx.strokeStyle = '#4a402b'; ctx.lineWidth = Math.max(1, r * .16);
      ctx.beginPath(); ctx.moveTo(base.x, base.y); ctx.lineTo(top.x, top.y); ctx.stroke();
      ctx.fillStyle = m.color || '#e9a769';
      ctx.beginPath(); ctx.ellipse(base.x, base.y - r * .9, r * .8, r * 1.45, 0, 0, TAU); ctx.fill();
      ctx.strokeStyle = '#fff0cb'; ctx.lineWidth = Math.max(1, r * .13); ctx.stroke();
      if (m.index === activeMark) {
        ctx.fillStyle = '#ffdf9a'; ctx.beginPath();
        ctx.moveTo(top.x, top.y); ctx.lineTo(top.x + r * 2.2, top.y + r * .35 + 2 * Math.sin(time * 4));
        ctx.lineTo(top.x, top.y + r * .8); ctx.closePath(); ctx.fill();
        ctx.font = '700 12px Segoe UI, sans-serif'; ctx.textAlign = 'center';
        const label = `${m.name || 'Mark'}  ${Math.round(Math.hypot(m.x - cam.x, m.y - cam.y))} m`;
        const boxW = Math.min(190, ctx.measureText(label).width + 16);
        ctx.fillStyle = 'rgba(9,32,43,.82)'; ctx.fillRect(base.x - boxW / 2, top.y - 26, boxW, 19);
        ctx.fillStyle = '#ffedc7'; ctx.fillText(label, base.x, top.y - 12);
      }
    }
  }

  function drawWake(ctx, cam, boat, trail, time) {
    const points = (trail || []).slice(-85);
    if (points.length > 1) {
      for (let i = 1; i < points.length; i++) {
        const a = toCamera(cam, points[i-1].x, points[i-1].y, .035);
        const b = toCamera(cam, points[i].x, points[i].y, .035);
        drawLine(ctx, cam, a, b, `rgba(223,243,226,${.04 + .28 * i / points.length})`, 1 + i / points.length * 2.6);
      }
    }
    if ((boat.speed || 0) < .2) return;
    const f = { x: Math.sin(boat.heading), y: Math.cos(boat.heading) };
    const r = { x: Math.cos(boat.heading), y: -Math.sin(boat.heading) };
    for (let side of [-1, 1]) for (let k = 0; k < 5; k++) {
      const t = 1 + k * 1.4;
      const x = boat.x - f.x * (2 + t) + r.x * side * (.65 + .19 * t);
      const y = boat.y - f.y * (2 + t) + r.y * side * (.65 + .19 * t);
      const p = projectWorld(cam, x, y, .07 + .02 * Math.sin(time * 5 + k));
      if (!p.visible || p.x < -20 || p.x > cam.width + 20 || p.y < 0 || p.y > cam.height) continue;
      const size = clamp(24 / p.depth, 1, 8);
      ctx.strokeStyle = `rgba(235,246,228,${.22 * (1 - k / 6)})`; ctx.lineWidth = size * .42;
      ctx.beginPath(); ctx.moveTo(p.x - size, p.y); ctx.lineTo(p.x + size, p.y - size * .2); ctx.stroke();
    }
  }

  function drawBoat(ctx, cam, boat, time) {
    const heading = boat.heading || 0;
    const f = { x: Math.sin(heading), y: Math.cos(heading) };
    const r = { x: Math.cos(heading), y: -Math.sin(heading) };
    const heel = boat.heel || 0, ch = Math.cos(heel), sh = Math.sin(heel);
    const bob = .055 * Math.sin(time * 2.1 + boat.x * .02);
    function V(side, ahead, z) {
      const relativeZ = z - .22;
      const s = side * ch + relativeZ * sh;
      const up = .22 - side * sh + relativeZ * ch + bob;
      return toCamera(cam, boat.x + f.x * ahead + r.x * s,
        boat.y + f.y * ahead + r.y * s, up);
    }
    function face(coords, fill, stroke, lw) {
      drawPoly(ctx, cam, coords.map(v => V(v[0], v[1], v[2])), fill, stroke, lw);
    }
    function line(a, b, color, lw) { drawLine(ctx, cam, V(...a), V(...b), color, lw); }

    const bow = [0, 2.43, .45], pl = [-.75, -2.31, .44], pr = [.75, -2.31, .44];
    const pMid = [-.81, -.15, .50], sMid = [.81, -.15, .50];
    const pNose = [-.48, 1.72, .48], sNose = [.48, 1.72, .48];
    if (cam.mode === 'chase') {
      face([[-.64,-2.31,-.05], [.64,-2.31,-.05], pr, pl], '#163b56', '#a8c4c5', 1.2);
      face([pr, sMid, sNose, bow, [0,2.43,-.04], [.61,-.15,-.12], [.64,-2.31,-.05]],
        boat.capsized ? '#1b3440' : '#1c4b68', '#0d3347', 1);
      face([pl, pMid, pNose, bow, [0,2.43,-.04], [-.61,-.15,-.12], [-.64,-2.31,-.05]],
        boat.capsized ? '#1b3440' : '#245873', '#0d3347', 1);
      face([pl, pMid, pNose, bow, sNose, sMid, pr], '#b27d43', '#f4d49a', 2.4);
      face([[-.58,-2.12,.47],[-.62,-.1,.51],[-.37,1.70,.49],[0,2.22,.50],[.37,1.70,.49],[.62,-.1,.51],[.58,-2.12,.47]],
        boat.capsized ? '#365661' : '#e8e6d8', '#9e6c39', 1.7);
    } else {
      face([[-.62,-.85,.49],[-.62,-.1,.51],[-.37,1.70,.49],[0,2.32,.50],[.37,1.70,.49],[.62,-.1,.51],[.62,-.85,.49]],
        '#eae8da', '#c59051', 2.2);
    }
    // Triangular foredeck, centreboard case and transverse seats.
    face([[-.35,1.69,.51], bow, [.35,1.69,.51]], '#bc8650', '#f4d69e', 1.5);
    face([[-.13,-.16,.58],[.13,-.16,.58],[.12,.95,.56],[-.12,.95,.56]], '#9a6036', '#cf9a60', 1.4);
    for (const a of (cam.mode === 'first' ? [.60, 1.26] : [-1.30, .60, 1.26])) {
      const beam = a > 1 ? .40 : .67;
      face([[-beam,a-.105,.56],[beam,a-.105,.56],[beam,a+.11,.56],[-beam,a+.11,.56]],
        '#ad7542', '#e6bd7b', 1.3);
    }
    // Varnished rails, spaced blocks and the squared off transom.
    for (const side of [-1, 1]) {
      line([side*.75,-2.30,.49],[side*.81,-.15,.54], '#e7bd7f', 3.3);
      line([side*.81,-.15,.54],[side*.48,1.72,.51], '#e7bd7f', 3.1);
      line([side*.48,1.72,.51],bow, '#e7bd7f', 2.8);
      if (cam.mode === 'chase') for (let i = 0; i < 7; i++) {
        const a = -1.85 + i * .43, beam = .78 - .08 * Math.max(0, a);
        line([side*(beam-.12),a,.52],[side*beam,a,.55], '#d5a16b', 2);
      }
    }
    if (cam.mode === 'chase') {
      line(pl,pr,'#e4b879',3.4);
      const tiller = boat.rudder || 0;
      line([0,-2.30,.58],[clamp(tiller,-1,1)*-.45,-1.03,.82], '#80542f', 3.3);
      // Sailor in the cockpit, slightly to port of the over shoulder camera.
      const sailorSide = -.25 + (boat.crew || 0) * .42;
      const body = projectCamera(cam,V(sailorSide,-.84,1.04));
      const head = projectCamera(cam,V(sailorSide,-.79,1.46));
      if (body.visible && head.visible) {
        const size = clamp(cam.focal * .27 / head.depth, 6, 58);
        ctx.fillStyle = '#4a7082';
        ctx.beginPath(); ctx.ellipse(body.x, body.y, size*.75, size*1.18, -.18, 0, TAU); ctx.fill();
        ctx.fillStyle = '#d5a45b';
        ctx.fillRect(body.x-size*.64,body.y-size*.1,size*1.28,size*.2);
        ctx.fillStyle = '#d19b74';
        ctx.beginPath(); ctx.ellipse(head.x, head.y, size*.56, size*.62, 0, 0, TAU); ctx.fill();
        ctx.fillStyle = '#333b39';
        ctx.beginPath(); ctx.ellipse(head.x, head.y-size*.35, size*.59, size*.26, -.1, 0, TAU); ctx.fill();
      }
    }

    // Hollow square timber mast, balanced lug yard and boom. The same sailAngle
    // used by the force model determines what the player sees during tacks/jibes.
    const hoist = clamp(boat.hoist == null ? 1 : boat.hoist, 0, 1);
    const sailA = boat.sailAngle || 0;
    const sailSide = Math.sin(sailA), aft = Math.cos(sailA);
    const mastBase = [0,1.27,.47], mastTop = [0,1.27,5.38];
    line(mastBase,mastTop,'#79502e',8);
    line([-.025,1.27,.5],[-.025,1.27,5.3],'#d7a460',3);
    if (!boat.capsized && hoist > .04) {
      const lower = .48 + .76 * hoist;
      const tack = [-.05,1.44,lower-.22];
      const clew = [3.22*sailSide,1.44-3.22*aft,lower-.37];
      const throat = [-.22*sailSide,1.76,lower+2.45*hoist];
      const peak = [2.98*sailSide,1.76-3.10*aft,lower+3.12*hoist];
      line(tack,clew,'#ab753d',5);
      line(throat,peak,'#a66c37',5);
      face([tack,clew,peak,throat], 'rgba(250,248,232,.89)', 'rgba(199,189,158,.94)', 1.6);
      for (let i = 1; i <= 4; i++) {
        const t = i / 5;
        const a = [tack[0]+(throat[0]-tack[0])*t,tack[1]+(throat[1]-tack[1])*t,tack[2]+(throat[2]-tack[2])*t];
        const b = [clew[0]+(peak[0]-clew[0])*t,clew[1]+(peak[1]-clew[1])*t,clew[2]+(peak[2]-clew[2])*t];
        line(a,b,'rgba(187,190,178,.46)',1);
      }
    } else {
      line([0,1.15,1.0],[.18,-1.7,.9], '#ddd3ae', 4);
    }
  }

  function renderScene(ctx, options) {
    if (!ctx || !options || !options.boat || !options.map || !options.map.water_polygon) return;
    const { boat, map } = options;
    const width = Number(options.width) || ctx.canvas.width;
    const height = Number(options.height) || ctx.canvas.height;
    const cam = makeCamera(boat, width, height, options.mode);
    const time = Number(options.time) || 0;
    const shoreline = shorelineFor(map);
    ctx.save();
    drawBackground(ctx, cam, time);
    drawWater(ctx, cam, shoreline, boat, time);
    drawShore(ctx, cam, shoreline);
    drawWake(ctx, cam, boat, options.trail, time);
    drawCourse(ctx, cam, options.marks, options.activeMark || 0, time);
    drawBoat(ctx, cam, boat, time);
    if (boat.capsized) {
      ctx.fillStyle = 'rgba(17,47,65,.18)'; ctx.fillRect(0,0,width,height);
    }
    ctx.restore();
  }

  return { renderScene, makeCamera, projectWorld, screenToGround, horizonY, pointInPolygon, simplifyRing };
});
