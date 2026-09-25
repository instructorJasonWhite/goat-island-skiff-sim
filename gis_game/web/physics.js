/* Small-boat sailing model. World coordinates: x east, y north; headings clockwise from north. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.GISSailing = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  const RAD = Math.PI / 180;
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const dot = (a, b) => a.x * b.x + a.y * b.y;
  const hypot = (v) => Math.hypot(v.x, v.y);
  const deg = (r) => r / RAD;
  const wrap = (r) => Math.atan2(Math.sin(r), Math.cos(r));

  function createBoat(opts = {}) {
    const vx = opts.vx || 0;
    const vy = opts.vy || 0;
    return {
      x: opts.x || 0, y: opts.y || 0,
      vx, vy, heading: opts.heading || 0, yawRate: 0,
      heel: 0, rollRate: 0, sailAngle: 0,
      sailSide: 1, sheet: 0.55, board: 1, rudderBlade: 1, hoist: 1, crew: 0,
      speed: Math.hypot(vx, vy), forwardSpeed: 0,
      leeway: 0, apparentWindSpeed: 0, apparentFrom: 0,
      apparentFromSigned: 0, trueFrom: 0,
      point: 'Beam reach', sailForce: 0, capsized: false,
      capsizeTimer: 0, rudder: 0,
    };
  }

  function apparentWind(trueWind, boatVelocity) {
    return { x: trueWind.x - boatVelocity.x, y: trueWind.y - boatVelocity.y };
  }

  function pointOfSail(angleDeg) {
    const a = Math.abs(angleDeg);
    if (a < 35) return 'In irons';
    if (a < 55) return 'Close hauled';
    if (a < 78) return 'Close reach';
    if (a < 113) return 'Beam reach';
    if (a < 153) return 'Broad reach';
    return 'Running';
  }

  function stepBoat(b, input, wind, dt) {
    dt = clamp(dt, 0, 0.05);
    if (!dt) return b;
    const askedSheet = clamp(input.sheet ?? b.sheet, 0, 1);
    const askedHoist = clamp(input.hoist ?? b.hoist, 0, 1);
    const askedBoard = clamp(input.board ?? b.board, 0, 1);
    const askedRudderBlade = clamp(input.rudderBlade ?? b.rudderBlade, 0, 1);
    b.sheet += clamp(askedSheet - b.sheet, -dt * 0.7, dt * 0.7);
    b.hoist += clamp(askedHoist - b.hoist, -dt * 0.19, dt * 0.19);
    b.board += clamp(askedBoard - b.board, -dt * 0.42, dt * 0.42);
    b.rudderBlade += clamp(askedRudderBlade - b.rudderBlade, -dt * 0.55, dt * 0.55);
    b.crew += clamp(clamp(input.crew ?? b.crew, -1, 1) - b.crew, -dt * 1.5, dt * 1.5);
    b.rudder += clamp(clamp(input.tiller ?? 0, -1, 1) - b.rudder, -dt * 2.4, dt * 2.4);

    const f = { x: Math.sin(b.heading), y: Math.cos(b.heading) };
    const r = { x: Math.cos(b.heading), y: -Math.sin(b.heading) };
    const aw = apparentWind(wind, { x: b.vx, y: b.vy });
    const awSpeed = hypot(aw);
    const incoming = { x: -aw.x, y: -aw.y };
    const windFromF = dot(incoming, f);
    const windFromR = dot(incoming, r);
    const signedFromAngle = deg(Math.atan2(windFromR, windFromF));
    const trueIncoming = { x: -wind.x, y: -wind.y };
    b.trueFrom = deg(Math.abs(Math.atan2(dot(trueIncoming, r), dot(trueIncoming, f))));
    b.apparentWindSpeed = awSpeed;
    b.apparentFromSigned = signedFromAngle;
    b.apparentFrom = Math.abs(signedFromAngle);
    b.point = pointOfSail(b.trueFrom);

    // The boom crosses during a tack or jibe, but its inertia prevents an instant flip.
    // windFromR is positive for starboard wind; the boom lies on the opposite, leeward side.
    if (Math.abs(windFromR) > Math.max(0.18, awSpeed * 0.025)) b.sailSide = -Math.sign(windFromR);
    const targetSailAngle = b.sailSide * (80 - 66 * b.sheet) * RAD;
    b.sailAngle += clamp(targetSailAngle - b.sailAngle, -dt * 3.2, dt * 3.2);

    let sailFx = 0, sailFy = 0;
    if (!b.capsized && awSpeed > 0.1 && b.hoist > 0.025) {
      // Thin-sail lift and pressure drag use the apparent wind and actual boom angle.
      const sn = Math.sin(b.sailAngle), cs = Math.cos(b.sailAngle);
      // The clew lies aft and leeward; the aerodynamic chord points from clew to mast.
      const chord = { x: f.x * cs - r.x * sn, y: f.y * cs - r.y * sn };
      const normal = { x: r.x * cs + f.x * sn, y: r.y * cs + f.y * sn };
      const au = { x: aw.x / awSpeed, y: aw.y / awSpeed };
      const crossFlow = dot(au, normal);
      const incidence = Math.asin(clamp(Math.abs(crossFlow), 0, 1));
      const lift = Math.max(0, 1.21 * Math.sin(2 * incidence));
      const drag = 0.045 + 1.18 * Math.sin(incidence) ** 2;
      // A luffing lug sail loses most of its coherent lift in the no-go zone.
      const luff = 0.045 + 0.955 * clamp((b.apparentFrom - 19) / 25, 0, 1);
      const q = 0.5 * 1.225 * 9.2 * awSpeed * awSpeed * b.hoist ** 1.35 * luff;
      const side = Math.sign(crossFlow);
      sailFx = q * (normal.x * side * lift + au.x * drag);
      sailFy = q * (normal.y * side * lift + au.y * drag);
      // A strongly stalled sail has less useful attached flow.
      if (Math.abs(dot(au, chord)) < 0.08) {
        sailFx *= 0.83;
        sailFy *= 0.83;
      }
    }
    b.sailForce = Math.hypot(sailFx, sailFy);
    const sf = sailFx * f.x + sailFy * f.y;
    const sl = sailFx * r.x + sailFy * r.y;
    const vf = b.vx * f.x + b.vy * f.y;
    const vl = b.vx * r.x + b.vy * r.y;

    // Centerboard and hull resist leeway separately. Lifting the board increases drift.
    const forwardDrag = 12 * vf + 31 * vf * Math.abs(vf);
    const lateralDrag = (25 + 315 * b.board) * vl + (16 + 118 * b.board) * vl * Math.abs(vl);
    const hullWindage = b.capsized ? 0.85 : 0.10;
    const fx = (sf - forwardDrag) * f.x + (sl - lateralDrag) * r.x + wind.x * hullWindage;
    const fy = (sf - forwardDrag) * f.y + (sl - lateralDrag) * r.y + wind.y * hullWindage;
    b.vx += (fx / 165) * dt;
    b.vy += (fy / 165) * dt;

    // The rudder acts only when water moves over it. Reverse flow reverses steering.
    const rudderFlow = vf * Math.abs(vf);
    const rudderTorque = 220 * b.rudderBlade * rudderFlow * Math.sin(b.rudder * 45 * RAD);
    const weatherHelm = -sl * 0.007;
    // Water flowing past a centered rudder damps yaw once the tiller is released.
    const yawDamping = 220 + 350 * Math.abs(vf) * b.rudderBlade * (1 - Math.abs(b.rudder));
    const yawTorque = (b.capsized ? 0 : rudderTorque + weatherHelm) - yawDamping * b.yawRate;
    b.yawRate = clamp(b.yawRate + (yawTorque / 285) * dt, -1.0, 1.0);
    b.heading = wrap(b.heading + b.yawRate * dt);

    // Righting arm falls off after 45 degrees: sufficiently bad trim can capsize.
    const heelMoment = b.capsized ? 0 : sl * 2.05 + b.crew * 710;
    const restoring = -1750 * Math.sin(2 * b.heel);
    const rollTorque = heelMoment + restoring - 900 * b.rollRate;
    b.rollRate += rollTorque / 240 * dt;
    b.heel += b.rollRate * dt;
    if (!b.capsized && Math.abs(b.heel) > 68 * RAD) b.capsizeTimer += dt;
    else b.capsizeTimer = Math.max(0, b.capsizeTimer - dt * 2);
    if (b.capsizeTimer > 0.32 || Math.abs(b.heel) > 80 * RAD) {
      b.capsized = true;
      b.hoist = 0;
      b.rollRate = 0;
      b.heel = Math.sign(b.heel) * 93 * RAD;
    }
    if (b.capsized) b.heel = Math.sign(b.heel) * 93 * RAD;

    b.x += b.vx * dt;
    b.y += b.vy * dt;
    b.speed = Math.hypot(b.vx, b.vy);
    b.forwardSpeed = vf;
    b.leeway = deg(Math.atan2(vl, Math.max(0.15, Math.abs(vf))));
    return b;
  }

  // Seeded Ornstein-Uhlenbeck gusts: smooth, correlated speed and direction changes.
  function createWind(seed = 1337, baseSpeed = 6, fromDeg = 225, gustStrength = 1.7) {
    return { seed: seed >>> 0, baseSpeed, fromDeg, gustStrength, gust: 0, shift: 0, time: 0 };
  }
  function random(w) {
    w.seed = (1664525 * w.seed + 1013904223) >>> 0;
    return w.seed / 4294967296;
  }
  function normal(w) {
    return Math.sqrt(-2 * Math.log(Math.max(1e-10, random(w)))) * Math.cos(2 * Math.PI * random(w));
  }
  function stepWind(w, dt, x = 0, y = 0) {
    dt = clamp(dt, 0, 0.1);
    w.time += dt;
    w.gust += clamp(-w.gust * dt / 7 + 0.35 * w.gustStrength * Math.sqrt(dt) * normal(w), -dt * 5, dt * 5);
    w.shift += clamp(-w.shift * dt / 11 + 0.018 * Math.sqrt(dt) * normal(w), -dt * 0.16, dt * 0.16);
    w.gust = clamp(w.gust, -Math.max(2.2, w.baseSpeed * 0.44), Math.max(3.4, w.baseSpeed * 0.52));
    w.shift = clamp(w.shift, -0.30, 0.30);
    // Slow wave fields add continuous location-dependent gusts and veer.
    const sx = (x + w.time * 1.8) / 470, sy = (y - w.time * 0.7) / 360;
    const spatialGust = w.gustStrength * (0.23 * Math.sin(sx) * Math.cos(sy) + 0.12 * Math.sin(1.9 * sx - 0.7 * sy));
    const spatialVeer = 0.045 * Math.sin(x / 390 - y / 510 + w.time / 28);
    const speed = Math.max(0.5, w.baseSpeed + w.gust + spatialGust);
    const toward = (w.fromDeg + 180) * RAD + w.shift + spatialVeer;
    return { x: speed * Math.sin(toward), y: speed * Math.cos(toward), speed,
      fromDeg: (w.fromDeg + deg(w.shift + spatialVeer) + 360) % 360, gust: w.gust + spatialGust };
  }

  return { createBoat, stepBoat, apparentWind, pointOfSail, createWind, stepWind, RAD, clamp };
});
