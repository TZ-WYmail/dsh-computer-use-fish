/** Explicit opt-in test: real input is confined to a temporary GTK fixture. */
import fs from 'node:fs';import path from 'node:path';import os from 'node:os';import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';import {fileURLToPath} from 'node:url';
import sharp from 'sharp';
import {apply} from '../index.js';import {cuaCall} from '../lib/cua.js';import {getSnapshot} from '../lib/snapshot.js';
const here=path.dirname(fileURLToPath(import.meta.url));
const work=fs.mkdtempSync(path.join(os.tmpdir(),'dsh-fish-fixture-'));fs.chmodSync(work,0o700);
process.env.DSH_FISH_DIAGNOSTICS=path.join(work,'motion-state.json');
const statePath=path.join(work,'state.json');const results=[];const tools=new Map();const cleanup=[];let approvals=0;
const wait=ms=>new Promise(r=>setTimeout(r,ms));
const state=()=>JSON.parse(fs.readFileSync(statePath,'utf8'));
const check=(name,ok,detail)=>{results.push({name,ok,detail});console.log(ok?'PASS':'FAIL',name,detail||'');};
const fixture=spawn('/usr/bin/python3',[path.join(here,'desktop-fixture.py'),statePath],{env:{...process.env,GDK_BACKEND:'x11'},stdio:['ignore','ignore','pipe']});
let fixtureError='';fixture.stderr.on('data',d=>fixtureError+=d);
let target;
try{
 for(let i=0;i<100;i++){
  if(fs.existsSync(statePath)&&state().ready){const list=await cuaCall('list_windows',{});target=list.windows?.find(w=>w.pid===fixture.pid);if(target)break;}
  if(fixture.exitCode!==null)throw Error('Fixture exited: '+fixtureError);
  await wait(100);
 }
 assert.ok(target,'temporary fixture must be visible');
 const agent={id:'fish-fixture-agent',session:{id:'fish-fixture-session'},options:{provider:'fixture',model:'fixture-image'}};
 const ctx={tools:{register(t){tools.set(t.name,t)}},on(event,fn){if(event==='dispose')cleanup.push(fn)},
  approval:{async request(req){assert.equal(req.agent,agent);assert.equal(getSnapshot()?.pid,fixture.pid);approvals++;return 'allowed-once'}},
  get(name){return name==='llm'?{async resolveModelInfo(){return {inputModalities:['text','image']}}}:name==='attachments'?{
   imageLimits:{maxImageBytes:20*1024*1024},async saveImage({data,mediaType,name}){fs.writeFileSync(path.join(work,name),data);return {attachmentId:'sha256:'+'a'.repeat(64),mediaType,bytes:data.length,name}}
  }:undefined},
 };
 apply(ctx,{ttlMs:30000,maxElements:500,allowedApps:[target.app_name],cursorTheme:'',nativeImage:'full',companionEnabled:true,companionSize:300});
 const run=async(name,args)=>{const value=await tools.get(name).execute(args,{agent,signal:new AbortController().signal});console.log(name,JSON.stringify(value).slice(0,700));return value};
 const observe=async()=>run('screen_observe',{window:String(fixture.pid),mode:'native'});
 await wait(1600);
 check('12 model tools registered',tools.size===12);
 let v=await observe();check('native capture uses real fixture',v.ok&&v.image?.bytes>0&&v.window?.pid===fixture.pid);
 await wait(200);
 const list=await cuaCall('list_windows',{});const pet=list.windows?.find(w=>w.title==='DSH Fat Fish Companion');
 check('real companion window exists',Boolean(pet));
 check('observation does not replace fixture focus',state().active);
 const textElement=v.elements?.find(e=>/Verification input/i.test(e.label));assert.ok(textElement,'input element exposed');
 v=await run('computer_type',{element:textElement.index,text:'Whale 42'});await wait(200);
 check('real text input readback',v.ok&&state().entry==='Whale 42',state().entry);
 v=await run('computer_key',{key:'ctrl+a'});await wait(200);
 check('real foreground hotkey selects text',v.ok&&state().selection.length===2&&state().selection[1]-state().selection[0]===8,state().selection);
 if(!v.ok)throw Error('Foreground input unavailable; further input tests stopped.');
 v=await run('computer_key',{key:'5'});await wait(200);
 check('real foreground key reaches fixture',v.ok&&state().entry==='5',state().entry);
 await observe();
 const snap=getSnapshot(),button=state().rects.button;
 const sx=snap.screenshotWidth/state().width,sy=snap.screenshotHeight/state().height;
 v=await run('computer_click',{x:Math.round((button.x+button.width/2)*sx),y:Math.round((button.y+button.height/2)*sy)});await wait(250);
 check('real pixel click increments counter',v.ok&&state().clicks===1,state().clicks);
 const motion=JSON.parse(fs.readFileSync(process.env.DSH_FISH_DIAGNOSTICS,'utf8'));
 const ready=motion.history.find(e=>e.phase==='ready'),dispatch=motion.history.find(e=>e.phase==='dispatch');
 check('real renderer reaches contact before input dispatch',Boolean(ready&&dispatch&&ready.at<=dispatch.at));
 check('rendered approach is visible before contact',Boolean(ready&&ready.at-motion.history.find(e=>e.phase==='approach').at>.2));
 const buttonPoint={x:Math.round((button.x+button.width/2)*sx),y:Math.round((button.y+button.height/2)*sy)};
 v=await run('computer_click',{element:1});await wait(200);
 check('AX token click still works without fabricated coordinates',v.ok&&state().clicks===2,state().clicks);
 v=await run('computer_double_click',buttonPoint);await wait(250);
 check('real double click delivers two clicks',v.ok&&state().clicks===4,state().clicks);
 v=await run('computer_right_click',buttonPoint);await wait(250);
 check('real right click reaches target with button 3',v.ok&&state().mouse_buttons.includes(3),state().mouse_buttons);
 // Capture the companion while it truthfully shows a pending action.
 const petWindow=(await cuaCall('list_windows',{})).windows?.find(w=>w.title==='DSH Fat Fish Companion');
 if(petWindow){const image=await cuaCall('get_window_state',{pid:petWindow.pid,window_id:petWindow.window_id,include_screenshot:true});if(image.screenshot_png_b64){fs.writeFileSync(path.join(work,'pet-preview.png'),Buffer.from(image.screenshot_png_b64,'base64'));}}
 const obs=await observe();const scrollElement=obs.elements?.find(e=>/Verification scroll region/i.test(e.label));
 const sr=state().rects.scroll,ss=getSnapshot();
 v=await run('computer_scroll',{direction:'down',amount:5,x:Math.round((sr.x+sr.width/2)*ss.screenshotWidth/state().width),y:Math.round((sr.y+sr.height/2)*ss.screenshotHeight/state().height)});await wait(300);
 check('real scroll changes adjustment',v.ok&&state().scroll>0,state().scroll);
 await observe();
 const slider=state().rects.slider,shot=getSnapshot();const mx=shot.screenshotWidth/state().width,my=shot.screenshotHeight/state().height;
 v=await run('computer_drag',{from_x:Math.round((slider.x+slider.width*.22)*mx),from_y:Math.round((slider.y+slider.height*.72)*my),to_x:Math.round((slider.x+slider.width*.72)*mx),to_y:Math.round((slider.y+slider.height*.72)*my),duration_ms:500});await wait(300);
 check('real drag changes slider',v.ok&&state().slider>45,state().slider);
 check('foreground paths actually requested approval',approvals>=3,approvals);
 if(process.env.FISH_PREVIEW_OUT){
  const image=await cuaCall('get_desktop_state',{});const bytes=image.screenshot_png_b64;
  if(bytes){
   const capture=Buffer.from(bytes,'base64');const meta=await sharp(capture).metadata();const logical=state();const fx=meta.width/logical.screen.width,fy=meta.height/logical.screen.height;
   // The fixture itself supplies its logical position and display geometry.
   const crop={left:Math.round(logical.origin[0]*fx+4),top:Math.round(logical.origin[1]*fy+4),width:Math.round(logical.width*fx-8),height:Math.round(logical.height*fy-8)};
   assert.ok(crop.left>=0&&crop.top>=0&&crop.left+crop.width<=meta.width&&crop.top+crop.height<=meta.height,'fixture crop stays inside the display');
   await sharp(capture).extract(crop).resize({width:1600,withoutEnlargement:true}).png().toFile(process.env.FISH_PREVIEW_OUT);
  }
 }
}finally{
 for(const fn of cleanup)await fn();fixture.kill('SIGTERM');
 if(!process.env.FISH_KEEP_SESSION)await cuaCall('end_session',{session:process.env.CUA_SESSION||'dsh-computer-use'}).catch(()=>{});
 fs.writeFileSync(path.join(work,'results.json'),JSON.stringify({results,approvals},null,2));
 console.log('TEST_WORK',work);
 fs.writeFileSync(new URL('../../fish-desktop-last-run.json',import.meta.url),JSON.stringify({work,results,approvals},null,2));
}
if(results.some(r=>!r.ok))process.exitCode=1;
