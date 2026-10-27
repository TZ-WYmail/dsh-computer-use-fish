/** Real GTK rendering for all variants; a counter replaces OS input. */
import fs from 'node:fs';import os from 'node:os';import path from 'node:path';import assert from 'node:assert/strict';
import {createCompanion} from '../lib/companion.js';import {cuaCall} from '../lib/cua.js';
const work=fs.mkdtempSync(path.join(os.tmpdir(),'dsh-rich-smoke-'));fs.chmodSync(work,0o700);const diagnosticsPath=path.join(work,'state.json');
const b=createCompanion({enabled:true,diagnosticsPath});const wait=ms=>new Promise(r=>setTimeout(r,ms));const results=[];let invokes=0;
try{
 await b.ready;b.setDisplay(await cuaCall('get_screen_size',{}));for(let i=0;i<80&&!b.status().calibrated;i++)await wait(100);
 assert.ok(b.status().connected&&b.status().calibrated,JSON.stringify(b.status()));
 for(const tool of ['computer_click','computer_double_click','computer_right_click','computer_drag','computer_scroll'])for(let v=0;v<3;v++){
  const actionId=tool+'-'+v,target={bounds:{x:100,y:100,width:1000,height:700},point:{x:900,y:550},fromPoint:tool==='computer_drag'?{x:650,y:550}:null,coordinateSpace:'driver'};
  b.publish({state:'executing',tool,actionId,target});let called=0;const began=Date.now();
  await b.perform({tool,actionId,target,durationMs:500,direction:'down'},async contact=>{
   invokes++;called++;const d=JSON.parse(fs.readFileSync(diagnosticsPath,'utf8'));assert.equal(d.motion.phase,'armed');assert.equal(d.motion.variant,v);assert.equal(d.tool,tool);contact();return {effect:'confirmed'};
  });
  assert.equal(called,1);results.push({tool,variant:v,readyMs:Date.now()-began});b.publish({state:'pending',tool,actionId,target});await wait(350);
  assert.ok(b.status().connected&&!b.status().error.includes('Traceback'),JSON.stringify(b.status()));
 }
 for(const tool of ['screen_observe','screen_zoom','computer_type','computer_key','computer_wait','app_list','app_launch'])for(let v=0;v<3;v++){
  b.publish({state:'executing',tool,actionId:tool+'-'+v,target:null});await wait(170);assert.ok(b.status().connected&&!b.status().error.includes('Traceback'));results.push({tool,variant:v,rendered:true});
 }
 const out={ok:true,realGtkVariants:results.length,simulatedInputCount:invokes,osInputSent:false,results};
 fs.writeFileSync(new URL('../../fish6-renderer-results.json',import.meta.url),JSON.stringify(out,null,2));console.log(JSON.stringify(out));
}finally{b.close()}
