const test = require('node:test');
const assert = require('node:assert/strict');
const MapView = require('../map_view.js');

const lake = {
  bounds_m: { min_x: -100, max_x: 100, min_y: -100, max_y: 100 },
  water_polygon: [[-100, -100], [100, -100], [100, 100], [-100, 100]],
  islands: [[[10, 10], [25, 10], [20, 25]]]
};

function recordingCanvas(width, height) {
  const visible = [];
  const bases = [];
  function context(calls) {
    return new Proxy({}, {
      get(_target, key) {
        if (key === 'measureText') return value => ({ width: String(value).length * 7 });
        return (...args) => { calls.push([key, ...args]); };
      },
      set() { return true; }
    });
  }
  const canvas = { width, height, getContext: () => context(visible) };
  canvas.ownerDocument = { createElement() {
    const calls = [];
    bases.push(calls);
    return { width: 0, height: 0, getContext: () => context(calls) };
  } };
  return { canvas, visible, bases };
}

test('map projection puts east right and north up', () => {
  const project = MapView.createProjector(lake, 240, 104);
  const center = project(0, 0), east = project(50, 0), north = project(0, 50);
  assert.deepEqual(center, { x: 120, y: 52 });
  assert.ok(east.x > center.x && east.y === center.y);
  assert.ok(north.y < center.y && north.x === center.x);
});

test('expanded map preserves the same lake extent at three times the resolution', () => {
  const small = MapView.createProjector(lake, 240, 104);
  const large = MapView.createProjector(lake, 720, 312);
  assert.ok(small(65, 28).x > small(0, 0).x, 'landmarks need visible spacing');
  for (const [x, y] of [[-100, -100], [0, 0], [65, 28], [100, 100]]) {
    const a = small(x, y), b = large(x, y);
    assert.ok(Math.abs(b.x - 3 * a.x) < 1e-8);
    assert.ok(Math.abs(b.y - 3 * a.y) < 1e-8);
  }
});

test('shoreline cache rebuilds when map identity or canvas dimensions change', () => {
  const output = recordingCanvas(240, 104);
  const painter = MapView.createPainter(output.canvas, { large: false });
  const boat = { x: 0, y: 0, heading: 0 };
  painter.draw(lake, boat, [], 0);
  assert.equal(output.bases.length, 1);
  painter.draw(lake, { ...boat, x: 20 }, [], 0);
  assert.equal(output.bases.length, 1, 'boat motion should not repaint shoreline');
  painter.draw({ ...lake, water_polygon: [[-90,-90],[90,-90],[90,90],[-90,90]] }, boat, [], 0);
  assert.equal(output.bases.length, 2, 'replacement map needs a new base');
  output.canvas.width = 720;
  painter.draw(lake, boat, [], 0);
  assert.equal(output.bases.length, 3, 'resized canvas needs a new base');
});

test('large map marks the boat at its world position, pointing at its heading', () => {
  const output = recordingCanvas(720, 312);
  const painter = MapView.createPainter(output.canvas, { large: true });
  const boat = { x: 50, y: 25, heading: Math.PI / 2 };
  painter.draw(lake, boat, [{ x: -40, y: 50, name: 'Windward buoy', color: '#f8a45b' }], 0);
  const expected = MapView.createProjector(lake, 720, 312)(50, 25);
  assert.ok(output.visible.some(([name, x, y]) => name === 'translate' && Math.abs(x - expected.x) < 1e-8 && Math.abs(y - expected.y) < 1e-8));
  assert.ok(output.visible.some(([name, angle]) => name === 'rotate' && angle === Math.PI / 2));
  assert.ok(output.visible.some(([name, value]) => name === 'fillText' && value === 'YOU ARE HERE'));
  assert.ok(output.visible.some(([name, value]) => name === 'fillText' && String(value).includes('Windward buoy')));
  assert.ok(output.visible.some(([name, value]) => name === 'fillText' && value === 'N'));
});

test('compact map also draws a directional boat marker over the shoreline', () => {
  const output = recordingCanvas(240, 104);
  MapView.createPainter(output.canvas, { large: false }).draw(
    lake, { x: -50, y: -25, heading: Math.PI }, [], 0);
  const expected = MapView.createProjector(lake, 240, 104)(-50, -25);
  assert.ok(output.visible.some(([name, x, y]) => name === 'translate' && Math.abs(x - expected.x) < 1e-8 && Math.abs(y - expected.y) < 1e-8));
  assert.ok(output.visible.some(([name, angle]) => name === 'rotate' && angle === Math.PI));
});
