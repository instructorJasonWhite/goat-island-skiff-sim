const test = require('node:test');
const assert = require('node:assert/strict');
const P = require('../physics.js');
const I = require('../input.js');
const map = require('../../maps/greenwood_usgs.json');

function inRing(x, y, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const a = ring[i], b = ring[j];
    if ((a[1] > y) !== (b[1] > y) &&
        x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]) inside = !inside;
  }
  return inside;
}

function onWater(x, y) {
  return inRing(x, y, map.water_polygon) &&
    !map.islands.some(ring => inRing(x, y, ring));
}

test('default Greenwood start makes measurable progress under sail', () => {
  const boat = P.createBoat({
    x: map.spawn.x_m,
    y: map.spawn.y_m,
    heading: map.spawn.heading_deg * P.RAD,
  });
  const wind = P.createWind(82437, map.wind.speed_mps, map.wind.from_deg, map.wind.gust_mps);
  const input = { tiller: 0, sheet: 0.55, crew: 0, board: 1, rudderBlade: 1, hoist: 1 };
  assert.ok(onWater(boat.x, boat.y), 'Start must be on the mapped lake');
  let shoreContacts = 0;
  for (let step = 0; step < 3000; step++) {
    const flow = P.stepWind(wind, 0.02, boat.x, boat.y);
    const oldX = boat.x, oldY = boat.y;
    P.stepBoat(boat, input, flow, 0.02);
    if (!onWater(boat.x, boat.y)) {
      boat.x = oldX; boat.y = oldY;
      boat.vx *= -.17; boat.vy *= -.17; boat.yawRate *= .65;
      shoreContacts++;
    }
  }
  const displacement = Math.hypot(boat.x - map.spawn.x_m, boat.y - map.spawn.y_m);
  assert.ok(displacement > 40, `The boat moved ${displacement.toFixed(1)} m in 60 s`);
  assert.ok(boat.speed > 1, `Default start should still be sailing after 60 s; final speed was ${boat.speed.toFixed(2)} m/s`);
  assert.equal(shoreContacts, 0, `The starting reach hit shore ${shoreContacts} times`);
});

test('a medium tiller drag makes a controlled turn and settles after release', () => {
  const boat = P.createBoat({ heading: 0, vy: 2 });
  const helm = I.tillerFromDrag(200, 290);
  const wind = { x: -7, y: 0 };
  const input = { tiller: helm, sheet: 0.55, crew: 0,
    board: 1, rudderBlade: 1, hoist: 1 };
  for (let step = 0; step < 120; step++) P.stepBoat(boat, input, wind, 0.02);
  const heldTurn = Math.abs(boat.heading) / P.RAD;
  for (let step = 0; step < 45; step++)
    P.stepBoat(boat, { ...input, tiller: 0 }, wind, 0.02);
  const coastTurn = (Math.abs(boat.heading) / P.RAD) - heldTurn;
  assert.ok(heldTurn > 20 && heldTurn < 65,
    `90 px drag should steer decisively without whipping around: ${heldTurn}°`);
  assert.ok(coastTurn < 15,
    `the boat should settle soon after releasing the tiller: ${coastTurn}°`);
});
