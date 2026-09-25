const test=require('node:test');
const assert=require('node:assert/strict');
const {tillerFromDrag,sheetFromWheel}=require('../input.js');
const {createBoat,stepBoat}=require('../physics.js');

test('mouse drag follows the tiller handle while the bow turns opposite',()=>{
  assert.equal(tillerFromDrag(200,200),0);
  assert.equal(tillerFromDrag(200,30),1);
  assert.equal(tillerFromDrag(200,370),-1);
  assert.ok(tillerFromDrag(200,330)<-0.6 && tillerFromDrag(200,330)>-0.75,
    'a 130 px drag should leave room before full tiller');
  const boat=createBoat({heading:0,vy:2});
  boat.hoist=0;
  for(let i=0;i<25;i++) stepBoat(boat,{tiller:tillerFromDrag(200,330),hoist:0},
    {x:0,y:0},.02);
  assert.ok(boat.heading<0,'tiller right should turn the bow to port');
});

test('small mouse drags give fine tiller control on both sides',()=>{
  const tillerStarboard=tillerFromDrag(200,240);
  const tillerPort=tillerFromDrag(200,160);
  assert.ok(tillerStarboard< -0.1 && tillerStarboard> -0.14,
    `40 px drag should produce a gentle helm command, got ${tillerStarboard}`);
  assert.equal(tillerPort,-tillerStarboard);
  assert.ok(tillerFromDrag(200,280)<tillerStarboard);
});

test('wheel up trims in and wheel down eases, with sheet limits',()=>{
  assert.ok(sheetFromWheel(.55,-100)>.55);
  assert.ok(sheetFromWheel(.55,100)<.55);
  assert.equal(sheetFromWheel(1,-1000),1);
  assert.equal(sheetFromWheel(0,1000),0);
});
