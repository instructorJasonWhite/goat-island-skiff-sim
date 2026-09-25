const test = require('node:test');
const assert = require('node:assert/strict');
const { createBoat, stepBoat } = require('../physics.js');
const { nextNeedleRotation, bearingLabel } = require('../wind_indicator.js');

test('wind needle follows apparent wind around a fixed bow marker', () => {
  const wind = { x: -5, y: 0 }; // Wind from east.
  const input = { tiller: 0, sheet: .55, crew: 0, board: 1, hoist: 0 };
  const north = createBoat({ heading: 0 });
  const east = createBoat({ heading: Math.PI / 2 });
  north.hoist = 0;
  east.hoist = 0;
  stepBoat(north, input, wind, .02);
  stepBoat(east, input, wind, .02);
  const acrossStarboard = nextNeedleRotation(north.apparentFromSigned, null);
  const overBow = nextNeedleRotation(east.apparentFromSigned, acrossStarboard);
  assert.ok(Math.abs(acrossStarboard) < .1, 'east wind should point right of the bow');
  assert.ok(Math.abs(overBow + 90) < .1, 'turning east should bring wind ahead');
  assert.equal(bearingLabel(north.apparentFromSigned).short, '90° STBD');
});

test('wind needle crosses astern by the short path during a jibe', () => {
  const before = nextNeedleRotation(179, null);
  const after = nextNeedleRotation(-179, before);
  assert.ok(Math.abs(after - before) < 5, `needle spun ${after - before}°`);
  assert.equal(bearingLabel(-90).short, '90° PORT');
});
