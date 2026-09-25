(function () {
  'use strict';
  const P = window.GISSailing;
  const V = window.GISView3D;
  const I = window.GISInput;
  const W = window.GISWindIndicator;
  const $ = (id) => document.getElementById(id);
  const canvas = $('lake'), ctx = canvas.getContext('2d');
  const mini = $('minimap'), expandedMap = $('largeMap'), mapDialog = $('mapDialog');
  const smallMapPainter = window.GISMapView.createPainter(mini, { large: false });
  const largeMapPainter = window.GISMapView.createPainter(expandedMap, { large: true });
  const keys = new Set();
  const mouseHelm = {active:false,startX:0,pointerId:null};
  const compass = ['N','NE','E','SE','S','SW','W','NW'];
  const FALLBACK = window.GISFallbackMap;
  let map = FALLBACK, boat, windSystem, wind = { x: 0, y: 0, speed: 0, fromDeg: 0, gust: 0 };
  let activeMark = 0, laps = 1, marks = [], paused = false, zoom = 1;
  let viewMode = 'chase', distanceSailed = 0;
  let controls = { tiller: 0, sheet: 0.55, crew: 0, board: 1, rudderBlade: 1, hoist: 1 };
  let width = 0, height = 0, scale = 0.7, camX = 0, camY = 0;
  let lastFrame = 0, accumulator = 0, uiTimer = 0, trackTimer = 0, toastTimer = 0;
  let trail = [], shoreCooldown = 0, inputSource = 'fallback';
  let mapWasPaused = false, mapReturnFocus = null;
  let windNeedleRotation = null;

  function resize() {
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    width = canvas.clientWidth; height = canvas.clientHeight;
    canvas.width = Math.round(width * dpr); canvas.height = Math.round(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    scale = Math.max(0.28, Math.min(2.4, Math.min(width / 1600, height / 1200) * zoom));
  }

  function pointInPolygon(x, y, polygon) {
    let inside = false;
    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
      const a = polygon[i], b = polygon[j];
      if (((a[1] > y) !== (b[1] > y)) && x < (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]) inside = !inside;
    }
    return inside;
  }
  function onWater(x, y) {
    if (!pointInPolygon(x, y, map.water_polygon)) return false;
    return !(map.islands || []).some(poly => pointInPolygon(x, y, poly));
  }
  function validMap(data) {
    if (!data || typeof data.name !== 'string' || !Array.isArray(data.water_polygon) || data.water_polygon.length < 3) return false;
    if (!data.water_polygon.every(p => Array.isArray(p) && p.length === 2 && p.every(Number.isFinite))) return false;
    const bounds=data.bounds_m;
    if (!bounds || ![bounds.min_x,bounds.max_x,bounds.min_y,bounds.max_y].every(Number.isFinite)) return false;
    if (!(bounds.min_x<bounds.max_x && bounds.min_y<bounds.max_y)) return false;
    if (!Array.isArray(data.islands || [])) return false;
    if (!(data.islands || []).every(poly => Array.isArray(poly) && poly.length>=3 && poly.every(p => Array.isArray(p) && p.length===2 && p.every(Number.isFinite)))) return false;
    if (!data.spawn || ![data.spawn.x_m, data.spawn.y_m, data.spawn.heading_deg].every(Number.isFinite)) return false;
    if (!data.wind || ![data.wind.from_deg, data.wind.speed_mps].every(Number.isFinite)) return false;
    if (data.wind.speed_mps<=0) return false;
    if (!pointInPolygon(data.spawn.x_m,data.spawn.y_m,data.water_polygon)) return false;
    if ((data.islands||[]).some(poly=>pointInPolygon(data.spawn.x_m,data.spawn.y_m,poly))) return false;
    return true;
  }
  function toast(message) {
    $('toast').textContent = message;
    $('toast').classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => $('toast').classList.remove('show'), 3500);
  }
  function chooseInside(dx, dy, fraction = 1) {
    let q = fraction, x, y;
    do {
      x = map.spawn.x_m + dx * q; y = map.spawn.y_m + dy * q;
      if (onWater(x, y)) return { x, y };
      q *= 0.72;
    } while (q > 0.1);
    return { x: map.spawn.x_m, y: map.spawn.y_m };
  }
  function makeCourse() {
    const a = map.wind.from_deg * P.RAD;
    const wx = Math.sin(a), wy = Math.cos(a), rx = Math.cos(a), ry = -Math.sin(a);
    marks = [
      { ...chooseInside(wx * 140, wy * 140), name: 'Windward buoy', color: '#f8a45b' },
      { ...chooseInside(wx * 45 + rx * 185, wy * 45 + ry * 185), name: 'Reach buoy', color: '#eccb83' },
      { ...chooseInside(-wx * 95 - rx * 70, -wy * 95 - ry * 70), name: 'Leeward buoy', color: '#88dcd2' },
    ];
    activeMark = 0; laps = 1;
  }
  function resetBoat() {
    boat = P.createBoat({ x: map.spawn.x_m, y: map.spawn.y_m, heading: map.spawn.heading_deg * P.RAD });
    controls = { tiller: 0, sheet: 0.55, crew: 0, board: 1, rudderBlade: 1, hoist: 1 };
    windSystem = P.createWind(82437, map.wind.speed_mps, map.wind.from_deg, map.wind.gust_mps || 1.7);
    wind = P.stepWind(windSystem, 0.02, boat.x, boat.y);
    P.stepBoat(boat, controls, wind, 0.02);
    trail = []; trackTimer = 0; distanceSailed = 0; windNeedleRotation = null;
    $('banner').hidden = true;
    $('sheet').value = 55; $('crew').value = 0;
    syncControls();
    camX = boat.x; camY = boat.y;
    updateHUD();
  }
  function useMap(data, source) {
    if (!validMap(data)) throw new Error('This JSON needs a water polygon, spawn point, and wind settings.');
    map = data; inputSource = source;
    $('lakeName').textContent = map.name;
    $('courseTitle').textContent = map.name.toUpperCase();
    $('mapWarning').textContent = map.approximate ? 'SCHEMATIC · NOT FOR NAVIGATION' : 'GIS SHORELINE · NOT FOR NAVIGATION';
    $('mapTag').textContent = map.approximate ? 'SCHEMATIC SHORELINE' : 'GIS SHORELINE';
    $('mapNotice').textContent = map.approximate
      ? 'Approximate practice map. Shorelines are not for navigation.'
      : 'GIS shoreline outline. Depth, hazards and live water levels are not modeled.';
    makeCourse(); resetBoat();
    toast(source === 'file' ? `Loaded ${map.name}` : `${map.name} ready for sailing`);
  }
  function loadMap(data, source) { useMap(data, source); }

  function screen(x, y) { return { x: width / 2 + (x - camX) * scale, y: height / 2 - (y - camY) * scale }; }
  function worldPath(context, polygon, projector = screen) {
    context.beginPath();
    polygon.forEach((p, i) => { const s = projector(p[0], p[1]); if (i) context.lineTo(s.x, s.y); else context.moveTo(s.x, s.y); });
    context.closePath();
  }
  function hash(a, b) {
    const q = Math.sin(a * 127.1 + b * 311.7) * 43758.5453123;
    return q - Math.floor(q);
  }

  function drawTerrain(t) {
    const terrain = ctx.createLinearGradient(0, 0, width, height);
    terrain.addColorStop(0, '#24463e'); terrain.addColorStop(.5, '#2e5141'); terrain.addColorStop(1, '#1b423e');
    ctx.fillStyle = terrain; ctx.fillRect(0, 0, width, height);
    const spacing = 46, halfW = width / 2 / scale, halfH = height / 2 / scale;
    const xa = Math.floor((camX - halfW) / spacing) - 1, xb = Math.ceil((camX + halfW) / spacing) + 1;
    const ya = Math.floor((camY - halfH) / spacing) - 1, yb = Math.ceil((camY + halfH) / spacing) + 1;
    for (let gx = xa; gx <= xb; gx++) for (let gy = ya; gy <= yb; gy++) {
      const x = gx * spacing + (hash(gx, gy) - .5) * 24;
      const y = gy * spacing + (hash(gy, gx) - .5) * 24;
      if (onWater(x, y)) continue;
      const p = screen(x, y), r = 6 + 11 * hash(gx + 4, gy + 1);
      ctx.fillStyle = hash(gx + 1, gy) > .5 ? 'rgba(11,48,39,.36)' : 'rgba(92,119,67,.29)';
      ctx.beginPath(); ctx.arc(p.x, p.y, r, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = 'rgba(7,37,34,.26)'; ctx.beginPath(); ctx.arc(p.x + r*.16, p.y + r*.18, r*.55, 0, Math.PI*2); ctx.fill();
    }

    ctx.save();
    worldPath(ctx, map.water_polygon);
    ctx.clip();
    const water = ctx.createLinearGradient(0, 0, width, height);
    water.addColorStop(0, '#285e62'); water.addColorStop(.42, '#1a5559'); water.addColorStop(1, '#104047');
    ctx.fillStyle = water; ctx.fillRect(0, 0, width, height);
    const waveSpacing = 26;
    const x0 = Math.floor((camX - halfW) / waveSpacing) - 1, x1 = Math.ceil((camX + halfW) / waveSpacing) + 1;
    const y0 = Math.floor((camY - halfH) / waveSpacing) - 1, y1 = Math.ceil((camY + halfH) / waveSpacing) + 1;
    ctx.lineWidth = 1.2;
    for (let gx = x0; gx <= x1; gx++) for (let gy = y0; gy <= y1; gy++) {
      if (hash(gx, gy) < .52) continue;
      const x = gx * waveSpacing + hash(gy, gx) * 10;
      const y = gy * waveSpacing + Math.sin(t * .6 + gx * .6 + gy) * 2;
      const p = screen(x, y), len = 4 + hash(gx + 9, gy) * 11;
      ctx.strokeStyle = `rgba(188,232,220,${.07 + .12 * hash(gx, gy + 4)})`;
      ctx.beginPath(); ctx.moveTo(p.x - len, p.y); ctx.quadraticCurveTo(p.x, p.y - 2, p.x + len, p.y); ctx.stroke();
    }
    ctx.restore();
    worldPath(ctx, map.water_polygon);
    ctx.strokeStyle = 'rgba(169,211,161,.34)'; ctx.lineWidth = 22; ctx.stroke();
    worldPath(ctx, map.water_polygon);
    ctx.strokeStyle = 'rgba(221,226,172,.6)'; ctx.lineWidth = 3; ctx.stroke();
    for (const island of map.islands || []) {
      worldPath(ctx, island); ctx.fillStyle = '#2d5340'; ctx.fill();
      ctx.strokeStyle = 'rgba(226,222,165,.6)'; ctx.lineWidth = 3; ctx.stroke();
    }
  }

  function drawMarks(t) {
    marks.forEach((m, i) => {
      const p = screen(m.x, m.y);
      if (p.x < -80 || p.x > width+80 || p.y < -80 || p.y > height+80) return;
      const active = i === activeMark;
      if (active) {
        ctx.strokeStyle = 'rgba(249,170,91,.36)'; ctx.lineWidth = 2;
        ctx.beginPath(); ctx.arc(p.x, p.y, 17 + 4 * Math.sin(t * 2), 0, Math.PI * 2); ctx.stroke();
      }
      ctx.fillStyle = 'rgba(4,27,31,.36)'; ctx.beginPath(); ctx.ellipse(p.x+3,p.y+7,7,4,0,0,Math.PI*2);ctx.fill();
      ctx.fillStyle = m.color; ctx.beginPath(); ctx.arc(p.x,p.y,active ? 7:5,0,Math.PI*2);ctx.fill();
      ctx.fillStyle = '#153b3e';ctx.beginPath();ctx.arc(p.x,p.y,2,0,Math.PI*2);ctx.fill();
      if (active) {
        ctx.font = '700 11px Segoe UI, sans-serif'; ctx.textAlign='center';
        ctx.fillStyle='rgba(7,31,35,.83)'; ctx.fillRect(p.x-47,p.y-34,94,20);
        ctx.fillStyle='#f8e5b8'; ctx.fillText(m.name, p.x,p.y-20);
      }
    });
  }

  function drawTrail() {
    if (trail.length < 2) return;
    ctx.lineWidth = 2;
    for (let i = 1; i < trail.length; i++) {
      const a = screen(trail[i-1].x,trail[i-1].y), b = screen(trail[i].x,trail[i].y);
      ctx.strokeStyle = `rgba(205,242,224,${(i/trail.length)*.2})`;
      ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();
    }
  }

  function drawBoat(t) {
    const p = screen(boat.x, boat.y), s = Math.max(12.2, Math.min(16, 13.6 * Math.sqrt(zoom)));
    ctx.save(); ctx.translate(p.x,p.y); ctx.rotate(boat.heading); ctx.scale(s,s);
    const heel = Math.sin(boat.heel);
    ctx.save(); ctx.translate(.12,.16); ctx.fillStyle='rgba(2,22,25,.34)';
    ctx.beginPath();ctx.moveTo(0,-2.48);ctx.bezierCurveTo(.65,-2.18,.89,.4,.66,2.32);ctx.lineTo(-.66,2.32);ctx.bezierCurveTo(-.89,.4,-.65,-2.18,0,-2.48);ctx.fill();ctx.restore();
    // Flat transom, fine bow, painted hull, pale cockpit and open varnished rails.
    ctx.beginPath();ctx.moveTo(0,-2.44);ctx.bezierCurveTo(.62,-2.12,.86,-.48,.71,1.62);ctx.lineTo(.67,2.31);ctx.lineTo(-.67,2.31);ctx.lineTo(-.71,1.62);ctx.bezierCurveTo(-.86,-.48,-.62,-2.12,0,-2.44);ctx.closePath();
    ctx.fillStyle=boat.capsized?'#1c3340':'#1e4b6a';ctx.fill();ctx.lineWidth=.08;ctx.strokeStyle='#c6a36a';ctx.stroke();
    ctx.beginPath();ctx.moveTo(0,-2.25);ctx.bezierCurveTo(.5,-1.97,.68,-.28,.56,1.57);ctx.lineTo(.51,2.13);ctx.lineTo(-.51,2.13);ctx.lineTo(-.56,1.57);ctx.bezierCurveTo(-.68,-.28,-.5,-1.97,0,-2.25);ctx.closePath();
    ctx.fillStyle=boat.capsized?'#2c5b62':'#e9e5d7';ctx.fill();
    ctx.save();ctx.clip();ctx.fillStyle=heel<0?'rgba(5,34,54,.19)':'rgba(244,249,218,.16)';ctx.fillRect(-1,-2.5,1,5);ctx.restore();
    ctx.fillStyle='#ba8144';
    ctx.beginPath();ctx.moveTo(0,-2.26);ctx.lineTo(.4,-1.65);ctx.lineTo(-.4,-1.65);ctx.closePath();ctx.fill();
    ctx.fillRect(-.54,-.23,1.08,.15);ctx.fillRect(-.53,1.26,1.06,.17);
    ctx.fillStyle='#986636';ctx.fillRect(-.12,-.05,.24,1.08);
    ctx.strokeStyle='#f4d8a3';ctx.lineWidth=.08;
    ctx.beginPath();ctx.moveTo(0,-2.44);ctx.bezierCurveTo(.62,-2.12,.86,-.48,.71,1.62);ctx.lineTo(.67,2.31);ctx.moveTo(0,-2.44);ctx.bezierCurveTo(-.62,-2.12,-.86,-.48,-.71,1.62);ctx.lineTo(-.67,2.31);ctx.stroke();
    for (let k=-1.5;k<1.9;k+=.38) {
      const u=.58+.15*Math.sin((k+1.6)/4*Math.PI);
      ctx.fillStyle='#c89455';ctx.fillRect(u,k,.08,.07);ctx.fillRect(-u-.08,k,.08,.07);
    }
    // Rudder stock and tiller rotate as one, with an exposed sliding blade.
    ctx.save();ctx.translate(0,2.31);ctx.rotate(-boat.rudder*.47);ctx.strokeStyle='#80512f';ctx.lineWidth=.12;
    ctx.beginPath();ctx.moveTo(0,-1.28);ctx.lineTo(0,.16);ctx.stroke();
    ctx.fillStyle='#b78545';ctx.fillRect(-.12,.05,.24,.44);
    ctx.fillStyle='#967048';ctx.fillRect(-.15,.47,.30,.12+.30*boat.rudderBlade);ctx.restore();
    // The balanced lug is a single port-rigged sail. The boom switches sides continuously.
    const mastY=-1.37, a=boat.sailAngle, L=2.92*boat.hoist;
    const boomX=-Math.sin(a)*L, boomY=mastY+Math.cos(a)*L;
    const topX=boomX*.48-.17, topY=mastY+.18;
    if (boat.hoist>.04 && !boat.capsized) {
      ctx.fillStyle=`rgba(248,248,230,${.35+.42*boat.hoist})`;
      ctx.strokeStyle='rgba(212,226,209,.9)';ctx.lineWidth=.035;
      ctx.beginPath();ctx.moveTo(-.08,mastY);ctx.lineTo(topX,topY-.2);ctx.lineTo(boomX,boomY);ctx.lineTo(boomX*.36,mastY+.72);ctx.closePath();ctx.fill();ctx.stroke();
      ctx.strokeStyle='#b78443';ctx.lineWidth=.07;ctx.beginPath();ctx.moveTo(-.05,mastY+.04);ctx.lineTo(boomX,boomY);ctx.stroke();
      ctx.strokeStyle='rgba(220,224,204,.6)';ctx.lineWidth=.018;for(let j=1;j<=3;j++){ctx.beginPath();ctx.moveTo(-.04+(topX+.04)*j/4,mastY);ctx.lineTo(boomX*j/4,mastY+(boomY-mastY)*j/4);ctx.stroke()}
    } else if (!boat.capsized) {
      ctx.strokeStyle='#f2e7cb';ctx.lineWidth=.14;ctx.beginPath();ctx.moveTo(0,mastY);ctx.lineTo(-.2,1.2);ctx.stroke();
    }
    ctx.fillStyle='#9b6537';ctx.fillRect(-.13,mastY-.15,.26,.26);
    ctx.fillStyle='#3e5f72';ctx.beginPath();ctx.ellipse(boat.crew*.53,.61,.24,.36,0,0,Math.PI*2);ctx.fill();
    ctx.fillStyle='#e0a16b';ctx.beginPath();ctx.arc(boat.crew*.53,.31,.18,0,Math.PI*2);ctx.fill();
    ctx.fillStyle='#ff9d4b';ctx.fillRect(boat.crew*.53-.18,.52,.36,.14);
    ctx.restore();
    if (boat.speed>.4) {
      const wake=screen(boat.x-Math.sin(boat.heading)*boat.speed*2,boat.y-Math.cos(boat.heading)*boat.speed*2);
      ctx.strokeStyle='rgba(207,240,223,.24)';ctx.lineWidth=2;
      ctx.beginPath();ctx.moveTo(p.x,p.y);ctx.lineTo(wake.x,wake.y);ctx.stroke();
    }
  }

  function drawMini() {
    smallMapPainter.draw(map,boat,marks,activeMark);
    if (mapDialog.open) {
      largeMapPainter.draw(map,boat,marks,activeMark);
      const heading=((Math.round(boat.heading/P.RAD)%360)+360)%360;
      const target=marks[activeMark];
      $('mapDialogTitle').textContent=map.name;
      $('mapPositionText').textContent=`You are here · heading ${heading}° · ${Math.round(Math.hypot(target.x-boat.x,target.y-boat.y))} m to ${target.name}`;
    }
  }

  function syncControls() {
    $('sheetValue').textContent=Math.round(controls.sheet*100)+'%';
    $('crewValue').textContent=Math.abs(controls.crew)<.05?'CENTER':`${Math.round(Math.abs(controls.crew)*100)}% ${controls.crew<0?'PORT':'STARBOARD'}`;
    $('board').querySelector('b').textContent=controls.board?'DOWN':'UP';
    $('rudderBlade').querySelector('b').textContent=controls.rudderBlade?'DOWN':'UP';
    $('hoist').querySelector('b').textContent=controls.hoist?'RAISED':'LOWERED';
    $('sheet').value=Math.round(controls.sheet*100);$('crew').value=Math.round(controls.crew*100);
  }
  function updateHUD() {
    $('speed').textContent=(boat.speed*1.94384).toFixed(1);
    $('distanceSailed').textContent=`${Math.round(distanceSailed)} m sailed`;
    $('point').textContent=boat.point;
    const bearing=W.bearingLabel(boat.apparentFromSigned);
    $('apparent').textContent=bearing.short;
    $('heel').textContent=`${Math.round(Math.abs(boat.heel)/P.RAD)}° ${boat.heel<0?'PORT':'STBD'}`;
    $('leeway').textContent=`${Math.round(Math.abs(boat.leeway))}°`;
    $('windReadout').textContent=`Apparent ${(boat.apparentWindSpeed*1.94384).toFixed(1)} kt`;
    $('windFrom').textContent=bearing.detail;
    $('trueWind').textContent=`True ${compass[Math.round(wind.fromDeg/45)%8]} ${(wind.speed*1.94384).toFixed(1)} kt · ${wind.gust>=.35?'gusting':wind.gust<=-.35?'lull':'steady'}`;
    windNeedleRotation=W.nextNeedleRotation(boat.apparentFromSigned,windNeedleRotation);
    $('windArrow').style.transform=`rotate(${windNeedleRotation}deg)`;
    const risk=P.clamp(Math.abs(boat.heel)/P.RAD/70,0,1);
    $('heelMeter').style.width=(risk*100).toFixed(0)+'%';
    $('heelMeter').style.background=risk>.72?'#ff9977':risk>.45?'#f2ca88':'#7dd9d2';
    $('riskLabel').textContent=risk>.72?'HIGH':risk>.45?'RISING':'LOW';
    $('riskLabel').style.color=risk>.72?'#ff9977':risk>.45?'#f2ca88':'#7dd9d2';
    const target=marks[activeMark],dist=Math.hypot(target.x-boat.x,target.y-boat.y);
    $('courseMark').textContent=target.name;$('courseDist').textContent=Math.round(dist)+' m';$('lap').textContent=`Lap ${laps}`;
    $('status').textContent=boat.capsized?'Capsized · press R to recover':boat.point==='In irons'&&boat.speed<.65?'In irons · ease the sheet and wait for flow over the rudder':`${boat.point} · ${Math.round(boat.trueFrom)}° true wind angle`;
    drawMini();
  }

  function update(dt) {
    if (keys.has('ArrowLeft')) controls.tiller=-1;
    else if (keys.has('ArrowRight')) controls.tiller=1;
    else if (!keys.has('PointerPort')&&!keys.has('PointerStarboard')&&!mouseHelm.active) controls.tiller=0;
    if(keys.has('KeyW'))controls.sheet=P.clamp(controls.sheet+dt*.42,0,1);
    if(keys.has('KeyS'))controls.sheet=P.clamp(controls.sheet-dt*.42,0,1);
    if(keys.has('KeyA'))controls.crew=P.clamp(controls.crew-dt*.65,-1,1);
    if(keys.has('KeyD'))controls.crew=P.clamp(controls.crew+dt*.65,-1,1);
    wind=P.stepWind(windSystem,dt,boat.x,boat.y);
    const oldX=boat.x,oldY=boat.y;
    P.stepBoat(boat,controls,wind,dt);
    if (!onWater(boat.x,boat.y)) {
      boat.x=oldX;boat.y=oldY;boat.vx*=-.17;boat.vy*=-.17;boat.yawRate*=.65;
      if(shoreCooldown<=0){toast('Shore ahead — turn back toward open water');shoreCooldown=5}
    }
    distanceSailed += Math.hypot(boat.x-oldX,boat.y-oldY);
    shoreCooldown-=dt;
    if (!boat.capsized) {
      const target=marks[activeMark];
      if (Math.hypot(target.x-boat.x,target.y-boat.y)<14) {
        const name=target.name;activeMark=(activeMark+1)%marks.length;
        if(activeMark===0){laps++;toast(`Course complete — lap ${laps}!`)}else toast(`${name} rounded`);
      }
    } else if ($('banner').hidden) {
      $('bannerTitle').textContent='CAPSIZED';
      $('bannerText').textContent='The sail overpowered the hull. Recover, then ease the sheet or move your weight to windward.';
      $('banner').hidden=false;
    }
    trackTimer+=dt;
    if(trackTimer>.22){trail.push({x:boat.x,y:boat.y});if(trail.length>230)trail.shift();trackTimer=0}
    uiTimer+=dt;if(uiTimer>.11){syncControls();updateHUD();uiTimer=0}
  }

  function render(t) {
    ctx.clearRect(0,0,width,height);
    if (V && V.renderScene) {
      V.renderScene(ctx,{width,height,boat,map,wind,marks,trail,time:t,mode:viewMode,activeMark});
    } else {
      camX+=(boat.x-camX)*.06;camY+=(boat.y-camY)*.06;
      drawTerrain(t);drawTrail();drawMarks(t);drawBoat(t);
    }
  }
  function frame(ms) {
    if(!lastFrame)lastFrame=ms;
    let elapsed=Math.min(.1,(ms-lastFrame)/1000);lastFrame=ms;
    if(!paused){accumulator+=elapsed;while(accumulator>=.02){update(.02);accumulator-=.02}}
    render(ms/1000);requestAnimationFrame(frame);
  }
  function togglePause(){paused=!paused;$('pause').textContent=paused?'Resume':'Pause';toast(paused?'Simulation paused':'Sailing resumed')}
  function openMap() {
    if (mapDialog.open) return;
    mapReturnFocus=document.activeElement;
    mapWasPaused=paused;
    paused=true;
    keys.clear();
    controls.tiller=0;
    $('pause').textContent='Resume';
    mapDialog.showModal();
    drawMini();
    $('closeMap').focus();
  }
  function closeMap() { if (mapDialog.open) mapDialog.close(); }
  function toggleView(){
    viewMode=viewMode==='chase'?'first':'chase';
    const first=viewMode==='first';
    $('viewToggle').textContent=first?'Third person · F':'First person · F';
    $('viewToggle').setAttribute('aria-pressed',String(first));
    canvas.setAttribute('aria-label',first?'First-person cockpit sailing view':'Third-person sailing view');
    toast(first?'Cockpit view':'Chase view');
  }
  function bindHeld(button,key,value){
    button.addEventListener('pointerdown',e=>{e.preventDefault();button.setPointerCapture(e.pointerId);keys.add(key);controls.tiller=value;button.classList.add('held')});
    const release=()=>{keys.delete(key);controls.tiller=0;button.classList.remove('held')};
    button.addEventListener('pointerup',release);button.addEventListener('pointercancel',release);button.addEventListener('lostpointercapture',release);
  }
  function bindControls(){
    $('openMap').addEventListener('click',openMap);
    $('openMapCompact').addEventListener('click',openMap);
    $('closeMap').addEventListener('click',closeMap);
    mapDialog.addEventListener('close',()=>{
      paused=mapWasPaused;
      $('pause').textContent=paused?'Resume':'Pause';
      if (mapReturnFocus && document.contains(mapReturnFocus)) mapReturnFocus.focus();
    });
    mapDialog.addEventListener('click',e=>{
      if(e.target!==mapDialog)return;
      const rect=mapDialog.getBoundingClientRect();
      if(e.clientX<rect.left||e.clientX>rect.right||e.clientY<rect.top||e.clientY>rect.bottom)closeMap();
    });
    canvas.addEventListener('pointerdown',e=>{
      if(e.pointerType!=='mouse'||e.button!==0)return;
      mouseHelm.active=true;mouseHelm.startX=e.clientX;mouseHelm.pointerId=e.pointerId;
      controls.tiller=0;canvas.setPointerCapture(e.pointerId);canvas.classList.add('dragging');e.preventDefault();
    });
    canvas.addEventListener('pointermove',e=>{
      if(!mouseHelm.active||e.pointerId!==mouseHelm.pointerId)return;
      controls.tiller=I.tillerFromDrag(mouseHelm.startX,e.clientX);
    });
    const endMouseHelm=()=>{mouseHelm.active=false;mouseHelm.pointerId=null;controls.tiller=0;canvas.classList.remove('dragging')};
    canvas.addEventListener('pointerup',endMouseHelm);
    canvas.addEventListener('pointercancel',endMouseHelm);
    canvas.addEventListener('lostpointercapture',endMouseHelm);
    canvas.addEventListener('wheel',e=>{e.preventDefault();controls.sheet=I.sheetFromWheel(controls.sheet,e.deltaY);syncControls()},{passive:false});
    window.addEventListener('keydown',e=>{
      if(mapDialog.open){if(e.code==='Space')e.preventDefault();return}
      if(['ArrowLeft','ArrowRight','Space','KeyW','KeyS','KeyA','KeyD'].includes(e.code))e.preventDefault();
      if(e.repeat&&['KeyC','KeyV','KeyH','KeyR','KeyF','Space'].includes(e.code))return;
      keys.add(e.code);
      if(e.code==='KeyC')controls.board=1-controls.board;
      if(e.code==='KeyV')controls.rudderBlade=1-controls.rudderBlade;
      if(e.code==='KeyH')controls.hoist=1-controls.hoist;
      if(e.code==='KeyR'){resetBoat();toast('Boat recovered at the start')}
      if(e.code==='KeyF')toggleView();
      if(e.code==='Space')togglePause();
      if(e.code==='Equal'||e.code==='NumpadAdd'){zoom=P.clamp(zoom*1.2,.55,3);resize()}
      if(e.code==='Minus'||e.code==='NumpadSubtract'){zoom=P.clamp(zoom/1.2,.55,3);resize()}
    });
    window.addEventListener('keyup',e=>keys.delete(e.code));
    window.addEventListener('blur',()=>{keys.clear();endMouseHelm()});
    $('sheet').addEventListener('input',e=>{controls.sheet=Number(e.target.value)/100;syncControls()});
    $('crew').addEventListener('input',e=>{controls.crew=Number(e.target.value)/100;syncControls()});
    $('board').addEventListener('click',()=>{controls.board=1-controls.board;syncControls()});
    $('rudderBlade').addEventListener('click',()=>{controls.rudderBlade=1-controls.rudderBlade;syncControls()});
    $('hoist').addEventListener('click',()=>{controls.hoist=1-controls.hoist;syncControls()});
    $('pause').addEventListener('click',togglePause);
    $('viewToggle').addEventListener('click',toggleView);
    $('bannerAction').addEventListener('click',()=>{resetBoat();toast('Boat recovered')});
    bindHeld($('port'),'PointerPort',-1);bindHeld($('starboard'),'PointerStarboard',1);
    $('loadMap').addEventListener('click',()=>$('mapFile').click());
    $('mapFile').addEventListener('change',async e=>{
      const file=e.target.files&&e.target.files[0];if(!file)return;
      try {loadMap(JSON.parse(await file.text()),'file')} catch(err){toast('Could not load map: '+err.message)}
      e.target.value='';
    });
    window.addEventListener('resize',resize);
  }
  async function start(){
    bindControls();resize();
    loadMap(FALLBACK,'fallback');
    requestAnimationFrame(frame);
    if(location.protocol!=='file:'){
      try {
        const param=new URLSearchParams(location.search).get('map');
        const sourceURL=new URL(param||'../maps/greenwood_usgs.json',location.href);
        if(sourceURL.origin===location.origin){
          const response=await fetch(sourceURL.href);if(!response.ok)throw Error(response.status);
          const found=await response.json();if(validMap(found))loadMap(found,'url');
        }
      } catch(err){console.warn('Using included lake map:',err)}
    }
  }
  start();
})();
