const test = require('node:test');
const assert = require('node:assert/strict');
const View = require('../view3d.js');

const boat = { x: 0, y: 0, heading: 0, heel: 0, speed: 2, sailAngle: .2,
  hoist: 1, rudder: 0, rudderBlade: 1, crew: 0, capsized: false };

test('chase camera follows boat and fixed shore moves across screen', () => {
  const cam1 = View.makeCamera(boat, 1000, 600, 'chase');
  const shore1 = View.projectWorld(cam1, 0, 100, 0);
  const cam2 = View.makeCamera({ ...boat, x: 12 }, 1000, 600, 'chase');
  const shore2 = View.projectWorld(cam2, 0, 100, 0);
  assert.equal(cam2.x - cam1.x, 12);
  assert.ok(shore1.visible && shore2.visible);
  assert.ok(shore2.x < shore1.x - 50, 'shore shifts visibly as boat travels east');
});

test('camera mode changes eye position and heading follows boat', () => {
  const chase = View.makeCamera(boat, 1000, 600, 'chase');
  const first = View.makeCamera(boat, 1000, 600, 'first');
  assert.ok(first.z < chase.z);
  assert.ok(first.y > chase.y);
  assert.ok(View.projectWorld(first, 0, 100).visible);
  const east = View.makeCamera({ ...boat, heading: Math.PI/2 }, 1000, 600, 'chase');
  assert.ok(View.projectWorld(east, 100, 0).visible);
  assert.ok(!View.projectWorld(east, -100, 0).visible);
});

test('screen ray returns the same ground point as perspective projection', () => {
  const cam = View.makeCamera({ ...boat, heading: .7, heel: .2 }, 1000, 600, 'first');
  const world = { x: 45, y: 55 };
  const image = View.projectWorld(cam, world.x, world.y, 0);
  assert.ok(image.visible);
  const ground = View.screenToGround(cam, image.x, image.y);
  assert.ok(Math.abs(ground.x - world.x) < 1e-7);
  assert.ok(Math.abs(ground.y - world.y) < 1e-7);
});

test('shoreline simplification preserves the ring and corner geometry', () => {
  const ring = [];
  for (let i = 0; i < 250; i++) ring.push([i * 2, 0]);
  ring.push([500, 300]);
  for (let i = 250; i > 0; i--) ring.push([i * 2, 300]);
  ring.push([0, 0]);
  const simple = View.simplifyRing(ring, 1.5);
  assert.ok(simple.length < ring.length / 4);
  assert.ok(simple.some(p => p[0] === 500 && p[1] === 300));
  assert.ok(simple.some(p => p[0] === 0 && p[1] === 0));
});

test('both camera views draw a complete scene with a dense shoreline', () => {
  const ring = [];
  for (let i = 0; i < 2000; i++) {
    const a = i * Math.PI * 2 / 2000;
    ring.push([550 * Math.cos(a), 330 * Math.sin(a)]);
  }
  const map = { water_polygon: ring, islands: [[[90,45],[115,48],[108,70],[88,68]]] };
  let calls = 0;
  const gradient = { addColorStop() {} };
  const ctx = new Proxy({}, { get(_target, key) {
    if (key === 'createLinearGradient') return () => gradient;
    if (key === 'measureText') return s => ({ width: String(s).length * 7 });
    return () => { calls++; };
  }, set() { return true; } });
  for (const mode of ['chase', 'first']) {
    View.renderScene(ctx, { width: 1000, height: 600, boat, map, mode,
      marks: [{ x: 0, y: 100, name: 'Mark', color: '#f90' }],
      activeMark: 0, trail: [{ x: 0, y: -2 }, { x: 0, y: -4 }], time: 4 });
  }
  assert.ok(calls > 100, `renderer issued ${calls} canvas calls`);
});

test('USGS shoreline leaves water beneath the Greenwood spawn boat', () => {
  const map = require('../../maps/greenwood_usgs.json');
  const atSpawn = { ...boat, x: map.spawn.x_m, y: map.spawn.y_m,
    heading: map.spawn.heading_deg * Math.PI / 180 };
  let paint = '', waterBelowBoat = false;
  const ctx = new Proxy({}, { get(_target, key) {
    if (key === 'createLinearGradient') return () => ({ addColorStop() {} });
    if (key === 'measureText') return s => ({ width: String(s).length * 7 });
    if (key === 'fillRect') return (x, y, w, h) => {
      if (typeof paint === 'string' && paint.startsWith('rgb(') && x <= 640 && x + w >= 640 && y <= 600 && y + h >= 600)
        waterBelowBoat = true;
    };
    return () => {};
  }, set(_target, key, value) { if (key === 'fillStyle') paint = value; return true; } });
  View.renderScene(ctx, { width: 1280, height: 720, boat: atSpawn, map, mode: 'chase', time: 0 });
  assert.ok(waterBelowBoat, 'water should cover the near foreground at the verified water spawn');
});

test('heeled cockpit paints water above the level horizon on the low side', () => {
  const heeled = { ...boat, heel: Math.PI / 6 };
  const cam = View.makeCamera(heeled, 1000, 600, 'first');
  const rightH = View.horizonY(cam, 1000), centerH = View.horizonY(cam, 500);
  const sampleY = Math.round((rightH + centerH) * .5);
  assert.ok(rightH < sampleY && sampleY < centerH,
    'starboard heel should make the apparent horizon rise to starboard');
  assert.ok(View.screenToGround(cam, 980, sampleY));
  assert.equal(View.screenToGround(cam, 500, sampleY), null);
  const map = { water_polygon: [[-10000,-10000],[10000,-10000],[10000,10000],[-10000,10000]], islands: [] };
  let paint = '', waterAtRight = false;
  const ctx = new Proxy({}, { get(_target, key) {
    if (key === 'createLinearGradient') return () => ({ addColorStop() {} });
    if (key === 'measureText') return s => ({ width: String(s).length * 7 });
    if (key === 'fillRect') return (x,y,w,h) => {
      if (typeof paint === 'string' && paint.startsWith('rgb(') &&
          x <= 980 && x+w >= 980 && y <= sampleY && y+h >= sampleY) waterAtRight = true;
    };
    return () => {};
  }, set(_target, key, value) { if (key === 'fillStyle') paint = value; return true; } });
  View.renderScene(ctx, { width: 1000, height: 600, boat: heeled, map, mode: 'first', time: 0 });
  assert.ok(waterAtRight, 'water follows the rolled horizon rather than a horizontal cutoff');
});

test('mast leans toward the same side named by heel', () => {
  const map = { water_polygon: [[-1000,-1000],[1000,-1000],[1000,1000],[-1000,1000]], islands: [] };
  function mastTilt(heel) {
    let strokeStyle = '', path = [], mast;
    const ctx = new Proxy({}, { get(_target, key) {
      if (key === 'createLinearGradient') return () => ({ addColorStop() {} });
      if (key === 'beginPath') return () => { path = []; };
      if (key === 'moveTo' || key === 'lineTo') return (x,y) => { path.push({x,y}); };
      if (key === 'stroke') return () => {
        if (strokeStyle === '#79502e' && path.length === 2) mast = path.slice();
      };
      return () => {};
    }, set(_target, key, value) { if (key === 'strokeStyle') strokeStyle = value; return true; } });
    View.renderScene(ctx, { width: 1000, height: 600,
      boat: { ...boat, heel, hoist: 0 }, map, mode: 'chase', time: 0 });
    assert.ok(mast, 'mast should be drawn');
    return mast[1].x - mast[0].x;
  }
  const upright = mastTilt(0);
  assert.ok(mastTilt(-Math.PI/9) < upright - 30,
    'port heel should lean the mast to port');
  assert.ok(mastTilt(Math.PI/9) > upright + 30,
    'starboard heel should lean the mast to starboard');
});

test('screen-row water mask agrees with a concave lake and island', () => {
  const map = {
    water_polygon: [[-100,-120],[100,-120],[100,100],[20,100],[20,20],[-20,20],[-20,100],[-100,100]],
    islands: [[[-8,8],[8,8],[8,16],[-8,16]]]
  };
  for (const mode of ['chase','first']) {
    const sailing = { ...boat, heel: mode === 'first' ? Math.PI/6 : 0 };
    const cam = View.makeCamera(sailing, 1000, 600, mode);
    const waterRects = [];
    let paint = '';
    const ctx = new Proxy({}, { get(_target, key) {
      if (key === 'createLinearGradient') return () => ({ addColorStop() {} });
      if (key === 'measureText') return s => ({ width: String(s).length * 7 });
      if (key === 'fillRect') return (x,y,w,h) => {
        if (typeof paint === 'string' && paint.startsWith('rgb(')) waterRects.push({x,y,w,h});
      };
      return () => {};
    }, set(_target,key,value) { if (key === 'fillStyle') paint = value; return true; } });
    View.renderScene(ctx,{width:1000,height:600,boat:sailing,map,mode,time:1});
    let checked = 0;
    for (let y = 104.5; y < 590; y += 6) for (let x = 25; x < 975; x += 75) {
      // Water strips are three pixels high; compare at their rendered centres.
      const stripY = Math.floor(y / 3) * 3 + 1.5;
      const p = View.screenToGround(cam,x,stripY);
      if (!p) continue; // the Canvas clip masks water strips above the rolled horizon
      const expected = !!p && View.pointInPolygon(p.x,p.y,map.water_polygon) &&
        !map.islands.some(island => View.pointInPolygon(p.x,p.y,island));
      const drawn = waterRects.some(r => x >= r.x+.2 && x < r.x+r.w-.2 && stripY >= r.y && stripY < r.y+r.h);
      if (expected !== drawn) {
        // Samples right on a coast can be raster-quantized by a fraction of a pixel.
        const nearby = [-.7,.7].some(dx => {
          const q = View.screenToGround(cam,x+dx,stripY);
          const nearWater = !!q && View.pointInPolygon(q.x,q.y,map.water_polygon) &&
            !map.islands.some(island => View.pointInPolygon(q.x,q.y,island));
          return nearWater !== expected;
        });
        if (!nearby) assert.equal(drawn,expected,`${mode} water mismatch at ${x},${stripY}`);
      }
      checked++;
    }
    assert.ok(checked > 500);
  }
});
