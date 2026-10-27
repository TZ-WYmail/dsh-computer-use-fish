/** Read-only desktop smoke: real GTK animation, a counter replaces desktop input. */
import fs from 'node:fs';import os from 'node:os';import path from 'node:path';import assert from 'node:assert/strict';
import {createCompanion} from '../lib/companion.js';import {cuaCall} from '../lib/cua.js';
const work=fs.mkdtempSync(path.join(os.tmpdir(),'dsh-jump-smoke-'));fs.chmodSync(work,0o700);const diagnosticsPath=path.join(work,'state.json');
const b=createCompanion({enabled:true,diagnosticsPath});const wait=ms=>new Promise(r=>setTimeout(r,ms));let invokes=0;const ys=[];
try{
 await b.ready;b.setDisplay(await cuaCall('get_screen_size',{}));
 for(let i=0;i<60&&!b.status().calibrated;i++)await wait(100);
 assert.ok(b.status().connected&&b.status().calibrated,JSON.stringify(b.status()));
 const target={bounds:{x:100,y:100,width:1000,height:700},point:{x:800,y:500},coordinateSpace:'driver'};
 b.publish({state:'executing',tool:'computer_click',actionId:'jump-smoke',target});
 let finished=false,landingY;
 const input=b.perform({tool:'computer_click',actionId:'jump-smoke',target},async contact=>{
  invokes++;const d=JSON.parse(fs.readFileSync(diagnosticsPath,'utf8'));assert.equal(d.motion.phase,'armed');assert.equal(d.motion.lift,0);landingY=d.position[1];contact();return {effect:'confirmed'};
 }).finally(()=>finished=true);
 while(!finished){const list=await cuaCall('list_windows',{});const w=list.windows?.find(w=>w.pid===b.pid&&w.title==='DSH Fat Fish Companion');if(w)ys.push(w.bounds.y);await wait(65)}
 await input;assert.equal(invokes,1);const measuredLift=landingY-Math.min(...ys);assert.ok(measuredLift>=65,JSON.stringify({landingY,ys}));
 const result={ok:true,simulatedInputCount:invokes,actualGtkJumpPixels:measuredLift,samples:ys.length,landingBeforeInput:true};
 fs.writeFileSync(new URL('../../fish5-renderer-results.json',import.meta.url),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
}finally{b.close()}
