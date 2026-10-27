import test from 'node:test';import assert from 'node:assert/strict';import net from 'node:net';import {once,EventEmitter} from 'node:events';
import {createCompanion} from '../lib/companion.js';import {dispatchInput} from '../lib/input-dispatch.js';
async function peer(){
 const bridge=createCompanion({enabled:true,launch:false});await bridge.ready
 bridge.setDisplay({width:1920,height:1200,mapping:{sx:1,sy:1,ox:0,oy:0}})
 const client=net.createConnection(bridge.socketPath);client.setEncoding('utf8');const events=new EventEmitter();let buffer=''
 client.on('data',d=>{buffer+=d;while(buffer.includes('\n')){const at=buffer.indexOf('\n');const value=JSON.parse(buffer.slice(0,at));buffer=buffer.slice(at+1);events.emit(value.type,value)}})
 await once(client,'connect');const initial=once(events,'state');client.write(JSON.stringify({type:'hello',token:bridge.token})+'\n');await initial
 return {bridge,client,events,close(){client.destroy();bridge.close()}}
}
const event={tool:'computer_double_click',target:{coordinateSpace:'driver',bounds:{x:0,y:0,width:100,height:100},point:{x:50,y:50}}}
test('contact acknowledgement precedes one dispatch; double click is one count=2 gesture',async()=>{
 const p=await peer(),phases=[];let inputs=0
 try{
  p.events.on('gesture',v=>{phases.push(v.phase);if(v.phase==='approach'){assert.equal(v.count,2);assert.equal(inputs,0);p.client.write(JSON.stringify({type:'gesture_ready',motionId:v.motionId})+'\n')}})
  await p.bridge.perform(event,async contact=>{inputs++;contact();return {effect:'confirmed'}})
  await new Promise(r=>setTimeout(r,10));assert.equal(inputs,1);assert.deepEqual(phases,['approach','dispatch','settle'])
 }finally{p.close()}
})
test('cancel during approach prevents any input and sends no contact',async()=>{
 const p=await peer(),abort=new AbortController();let inputs=0;const phases=[]
 try{
  p.events.on('gesture',v=>{phases.push(v.phase);if(v.phase==='approach')abort.abort()})
  await assert.rejects(p.bridge.perform(event,async()=>{inputs++},abort.signal),/取消/)
  await new Promise(r=>setTimeout(r,10));assert.equal(inputs,0);assert.ok(!phases.includes('dispatch'))
 }finally{p.close()}
})
test('renderer disconnection falls back to one ordinary input',async()=>{
 const p=await peer();let inputs=0
 try{
  p.events.on('gesture',v=>{if(v.phase==='approach')p.client.destroy()})
  await p.bridge.perform(event,async()=>{inputs++;return {effect:'confirmed'}});assert.equal(inputs,1)
 }finally{p.close()}
})
test('wrong gesture acknowledgement cannot trigger input',async()=>{
 const p=await peer(),abort=new AbortController();let inputs=0
 try{
  p.events.on('gesture',v=>{if(v.phase==='approach'){p.client.write('{"type":"gesture_ready","motionId":"stale"}\n');setTimeout(()=>abort.abort(),30)}})
  await assert.rejects(p.bridge.perform(event,async()=>inputs++,abort.signal));assert.equal(inputs,0)
 }finally{p.close()}
})
test('post-animation target validation prevents a stale click',async()=>{
 let clicks=0,frames=0
 await assert.rejects(dispatchInput(async()=>{clicks++},'click',{}, {presentInput:async invoke=>{frames++;return invoke(()=>{})},validateTarget:async()=>{throw Error('窗口移动')}}),/窗口移动/)
 assert.equal(frames,1);assert.equal(clicks,0)
})
test('foreground denial never starts a second presentation or dispatch',async()=>{
 let clicks=0,presentations=0
 const value=await dispatchInput(async()=>{clicks++;return {effect:'refused',code:'background_unavailable'}},'click',{}, {
  agent:{},approval:{async request(){return 'denied'}},validateTarget:async()=>{},presentInput:async invoke=>{presentations++;return invoke(()=>{})}})
 assert.equal(clicks,1);assert.equal(presentations,1);assert.equal(value.effect,'refused')
})
test('gesture metadata carries a scroll direction without input text',async()=>{
 const p=await peer();let observed
 try{
  p.events.on('gesture',v=>{if(v.phase==='approach'){observed=v;p.client.write(JSON.stringify({type:'gesture_ready',motionId:v.motionId})+'\n')}})
  await p.bridge.perform({...event,tool:'computer_scroll',direction:'up',text:'PRIVATE TEXT'},async contact=>{contact();return {effect:'confirmed'}})
  assert.equal(observed.direction,'up');assert.ok(!JSON.stringify(observed).includes('PRIVATE'))
 }finally{p.close()}
})
test('invalid direction metadata is replaced with a safe enum',async()=>{
 const p=await peer();let observed
 try{
  p.events.on('gesture',v=>{if(v.phase==='approach'){observed=v;p.client.write(JSON.stringify({type:'gesture_ready',motionId:v.motionId})+'\n')}})
  await p.bridge.perform({...event,direction:'PRIVATE VALUE'},async contact=>{contact();return {effect:'confirmed'}})
  assert.equal(observed.direction,'down');assert.ok(!JSON.stringify(observed).includes('PRIVATE'))
 }finally{p.close()}
})
