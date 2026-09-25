// Local visual QA fallback when an automated browser is unavailable.
const fs = require('node:fs');
const path = require('node:path');
let Canvas;
try { Canvas = require('@napi-rs/canvas'); }
catch { Canvas = require(path.resolve(path.dirname(process.execPath),'../node_modules/@napi-rs/canvas')); }
const { createCanvas } = Canvas;
const P = require('../physics.js');
const View = require('../view3d.js');
const map = require('../../maps/greenwood_usgs.json');

const boat = P.createBoat({ x: map.spawn.x_m, y: map.spawn.y_m,
  heading: map.spawn.heading_deg * P.RAD });
const windSystem = P.createWind(82437,map.wind.speed_mps,map.wind.from_deg,map.wind.gust_mps || 1.7);
const controls = { tiller:0, sheet:.55, crew:0, board:1, rudderBlade:1, hoist:1 };
let wind;
for (let i=0; i<1000; i++) {
  wind = P.stepWind(windSystem,.02,boat.x,boat.y);
  P.stepBoat(boat,controls,wind,.02);
}
const marks = [{ x: boat.x + 120, y: boat.y + 90, name:'Windward buoy', color:'#f8a45b' }];
const trail = [{x:boat.x-15,y:boat.y-5},{x:boat.x-5,y:boat.y-2}];
function save(name, mode, heel) {
  const canvas = createCanvas(1280,720);
  const ctx = canvas.getContext('2d');
  boat.heel = heel;
  for (let i=0; i<5; i++)
    View.renderScene(ctx,{width:1280,height:720,boat,map,wind,marks,trail,time:20+i*.02,mode,activeMark:0});
  const started = performance.now();
  for (let i=0; i<30; i++)
    View.renderScene(ctx,{width:1280,height:720,boat,map,wind,marks,trail,time:20+i*.02,mode,activeMark:0});
  console.log(`${mode} at ${Math.round(heel*180/Math.PI)} deg heel: ${((performance.now()-started)/30).toFixed(2)} ms/frame, Canvas 2D`);
  const file = path.join(__dirname,'..',name);
  fs.writeFileSync(file,canvas.toBuffer('image/png'));
  console.log(file);
}
save('view3d_chase_scene.png','chase',boat.heel);
save('view3d_cockpit_heel30_scene.png','first',Math.PI/6);
