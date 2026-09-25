const test = require('node:test');
const assert = require('node:assert/strict');
const {
  createBoat,
  stepBoat,
  apparentWind,
  pointOfSail,
  createWind,
  stepWind,
} = require('../physics.js');

const calmInput = { tiller: 0, sheet: 0.55, crew: 0, board: 1, hoist: 1 };

function advance(boat, seconds, wind, input = calmInput) {
  for (let i = 0; i < seconds / 0.02; i++) stepBoat(boat, input, wind, 0.02);
  return boat;
}

test('apparent wind includes boat velocity', () => {
  const a = apparentWind({ x: -5, y: 0 }, { x: -2, y: 0 });
  assert.equal(a.x, -3);
  assert.equal(a.y, 0);
});

test('apparent wind bearing stays relative to the bow as the boat turns', () => {
  const windFromEast = { x: -5, y: 0 };
  const windFromWest = { x: 5, y: 0 };
  const north = createBoat({ heading: 0 });
  const east = createBoat({ heading: Math.PI / 2 });
  const northPort = createBoat({ heading: 0 });
  for (const boat of [north, east, northPort]) boat.hoist = 0;
  stepBoat(north, { ...calmInput, hoist: 0 }, windFromEast, 0.02);
  stepBoat(east, { ...calmInput, hoist: 0 }, windFromEast, 0.02);
  stepBoat(northPort, { ...calmInput, hoist: 0 }, windFromWest, 0.02);
  assert.ok(Math.abs(north.apparentFromSigned - 90) < 0.1);
  assert.ok(Math.abs(east.apparentFromSigned) < 0.1);
  assert.ok(Math.abs(northPort.apparentFromSigned + 90) < 0.1);
});

test('sailing forces do not depend on map position', () => {
  const wind = { x: -7, y: 0 };
  const one = createBoat({ x: 0, y: 0, heading: 0 });
  const two = createBoat({ x: 1200, y: 800, heading: 0 });
  stepBoat(one, calmInput, wind, 0.02);
  stepBoat(two, calmInput, wind, 0.02);
  assert.ok(Math.abs(one.sailForce - two.sailForce) < 1e-9);
});

test('point of sail distinguishes irons, reaching, and running', () => {
  assert.equal(pointOfSail(0), 'In irons');
  assert.equal(pointOfSail(95), 'Beam reach');
  assert.equal(pointOfSail(176), 'Running');
});

test('point of sail uses true wind while apparent angle responds to speed', () => {
  const boat=createBoat({ heading: 0, vy: 3 });
  stepBoat(boat,calmInput,{ x:-7,y:0 },0.02);
  assert.equal(boat.point,'Beam reach');
  assert.ok(boat.apparentFrom<80);
});

test('the balanced lug sail lies to leeward of the apparent wind', () => {
  const fromPort = advance(createBoat({ heading: 0 }), 1,
    { x: 5, y: 0 });
  const fromStarboard = advance(createBoat({ heading: 0 }), 1,
    { x: -5, y: 0 });
  assert.ok(fromPort.apparentFromSigned < -70);
  assert.ok(fromStarboard.apparentFromSigned > 70);
  assert.equal(fromPort.sailSide, 1, 'port wind should put the sail to starboard');
  assert.equal(fromStarboard.sailSide, -1, 'starboard wind should put the sail to port');
  assert.ok(fromPort.sailAngle > 0);
  assert.ok(fromStarboard.sailAngle < 0);

  const portHeadwind = advance(createBoat({ heading: 0 }), 1,
    { x: 5 * Math.sin(15 * Math.PI / 180),
      y: -5 * Math.cos(15 * Math.PI / 180) });
  assert.ok(portHeadwind.apparentFromSigned < -10);
  assert.equal(portHeadwind.sailSide, 1,
    '15° port wind should luff with the sail on starboard');
});

test('beam reach gathers speed while head to wind stays in irons', () => {
  const wind = { x: -7, y: 0 };
  const reaching = advance(createBoat({ heading: 0 }), 12, wind);
  const inIrons = advance(createBoat({ heading: Math.PI / 2 }), 12, wind);
  assert.ok(reaching.speed > 1.2, `reach ${reaching.speed}`);
  assert.ok(inIrons.speed < reaching.speed * 0.45, `irons ${inIrons.speed}, reach ${reaching.speed}`);
});

test('rudder authority depends on water flow', () => {
  const still = createBoat({ heading: 0 });
  const moving = createBoat({ heading: 0, vx: 0, vy: 3 });
  const wind = { x: 0, y: 0 };
  advance(still, 0.5, wind, { ...calmInput, tiller: 1, hoist: 0 });
  advance(moving, 0.5, wind, { ...calmInput, tiller: 1, hoist: 0 });
  assert.ok(Math.abs(moving.yawRate) > Math.abs(still.yawRate) + 0.03);
});

test('released helm lets the boat settle instead of coasting through a turn', () => {
  const boat = createBoat({ heading: 0 });
  boat.hoist = 0;
  boat.yawRate = 0.5;
  advance(boat, 1, { x: 0, y: 0 }, { ...calmInput, tiller: 0, hoist: 0 });
  assert.ok(boat.yawRate < 0.24,
    `unsteered yaw should settle within a second, got ${boat.yawRate}`);
});

test('a centered immersed rudder steadies yaw as water flows past it', () => {
  const still = createBoat({ heading: 0 });
  const moving = createBoat({ heading: 0, vy: 2 });
  const bladeRaised = createBoat({ heading: 0, vy: 2 });
  for (const boat of [still, moving, bladeRaised]) {
    boat.hoist = 0;
    boat.yawRate = 0.5;
  }
  bladeRaised.rudderBlade = 0;
  advance(still, 1, { x: 0, y: 0 }, { ...calmInput, hoist: 0 });
  advance(moving, 1, { x: 0, y: 0 }, { ...calmInput, hoist: 0 });
  advance(bladeRaised, 1, { x: 0, y: 0 },
    { ...calmInput, hoist: 0, rudderBlade: 0 });
  assert.ok(moving.yawRate < still.yawRate * 0.4,
    `moving boat should settle faster: ${moving.yawRate} vs ${still.yawRate}`);
  assert.ok(moving.yawRate < bladeRaised.yawRate * 0.4,
    'raising the rudder blade should remove most of its stabilizing effect');
});

test('sliding rudder blade controls steering authority', () => {
  const down=createBoat({ heading:0,vy:2.6 });
  const up=createBoat({ heading:0,vy:2.6 });
  up.rudderBlade=0;
  const wind={ x:0,y:0 };
  advance(down,1.5,wind,{...calmInput,tiller:1,rudderBlade:1,hoist:0});
  advance(up,1.5,wind,{...calmInput,tiller:1,rudderBlade:0,hoist:0});
  assert.ok(Math.abs(down.heading)>Math.abs(up.heading)*1.6);
});

test('a slow tack can hang in irons while a faster tack passes through', () => {
  const wind={x:-7,y:0};
  const tack={...calmInput,tiller:1,crew:1,rudderBlade:1};
  const slow=advance(createBoat({heading:0,vy:0.4}),4.5,wind,tack);
  const fast=advance(createBoat({heading:0,vy:2}),4.5,wind,tack);
  assert.equal(slow.point,'In irons');
  assert.ok(slow.speed<0.5);
  assert.ok(fast.heading>125*Math.PI/180,`fast heading ${fast.heading*180/Math.PI}`);
  assert.equal(fast.sailSide,1, 'after tacking into port wind the sail lies to starboard');
});

test('a jibe crosses dead downwind and switches boom side', () => {
  const wind={x:-7,y:0};
  const input={...calmInput,sheet:0.25,tiller:0};
  const boat=advance(createBoat({heading:-50*Math.PI/180}),10,wind,input);
  const startSide=boat.sailSide;
  advance(boat,2,wind,{...input,tiller:-1});
  assert.ok(boat.heading<-115*Math.PI/180,`heading ${boat.heading*180/Math.PI}`);
  assert.equal(boat.sailSide,-startSide);
});

test('hiking to windward reduces heel', () => {
  const wind = { x: -11, y: 0 };
  const centered = advance(createBoat({ heading: 0 }), 7, wind, { ...calmInput, sheet: 0.8 });
  const hiking = advance(createBoat({ heading: 0 }), 7, wind, { ...calmInput, sheet: 0.8, crew: 1 });
  assert.ok(Math.abs(hiking.heel) < Math.abs(centered.heel), `hiking ${hiking.heel}, centered ${centered.heel}`);
});

test('lowered sail substantially reduces driving force', () => {
  const wind = { x: -8, y: 0 };
  const up = advance(createBoat({ heading: 0 }), 8, wind);
  const down = advance(createBoat({ heading: 0 }), 8, wind, { ...calmInput, hoist: 0 });
  assert.ok(up.speed > down.speed * 2, `up ${up.speed}, down ${down.speed}`);
});

test('centerboard reduces sideways drift', () => {
  const wind = { x: -9, y: 0 };
  const down = advance(createBoat({ heading: 0 }), 5, wind);
  const up = advance(createBoat({ heading: 0 }), 5, wind, { ...calmInput, board: 0 });
  assert.ok(Math.abs(up.vx) > Math.abs(down.vx) * 1.25, `up ${up.vx}, down ${down.vx}`);
});

test('strong wind and poor crew position can capsize', () => {
  const wind = { x: -20, y: 0 };
  const boat = advance(createBoat({ heading: 0 }), 20, wind, { ...calmInput, sheet: 0.8, crew: -1 });
  assert.equal(boat.capsized, true);
});

test('recovering creates a fresh upright boat', () => {
  const capsized=advance(createBoat({heading:0}),20,{x:-20,y:0},{...calmInput,sheet:0.8,crew:-1});
  assert.equal(capsized.capsized,true);
  const recovered=createBoat({x:10,y:20,heading:0});
  assert.equal(recovered.capsized,false);
  assert.equal(recovered.heel,0);
  assert.equal(recovered.rudderBlade,1);
});

test('wind evolves smoothly and remains near baseline', () => {
  const wind = createWind(12345, 6, 45);
  let previous = stepWind(wind, 0.05);
  for (let i = 0; i < 2000; i++) {
    const current = stepWind(wind, 0.05);
    assert.ok(Math.hypot(current.x - previous.x, current.y - previous.y) < 0.5);
    assert.ok(Math.hypot(current.x, current.y) > 2 && Math.hypot(current.x, current.y) < 12);
    previous = current;
  }
});

test('nearby places have similar wind while distant places differ', () => {
  const one=createWind(42,6,315);
  const two=createWind(42,6,315);
  const three=createWind(42,6,315);
  const a=stepWind(one,.02,0,0);
  const b=stepWind(two,.02,1,1);
  const c=stepWind(three,.02,700,400);
  assert.ok(Math.hypot(a.x-b.x,a.y-b.y)<0.03);
  assert.ok(Math.hypot(a.x-c.x,a.y-c.y)>0.12);
});
