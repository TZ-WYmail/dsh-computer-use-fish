import test from 'node:test'
import assert from 'node:assert/strict'
import net from 'node:net'
import { once } from 'node:events'
import { statSync } from 'node:fs'
import { createCompanion, presentationTarget } from '../lib/companion.js'

test('IPC is private, authenticated and excludes input text', async () => {
  const bridge=createCompanion({enabled:true,launch:false})
  try {
    await bridge.ready
    assert.equal(statSync(bridge.socketPath).mode & 0o777,0o600)
    const bad=net.createConnection(bridge.socketPath)
    await once(bad,'connect');bad.write('{"type":"hello","token":"wrong"}\n');await once(bad,'close')
    const client=net.createConnection(bridge.socketPath);client.setEncoding('utf8')
    await once(client,'connect')
    const initial=once(client,'data');client.write(JSON.stringify({type:'hello',token:bridge.token})+'\n');await initial
    const received=once(client,'data')
    bridge.publish({state:'executing',tool:'computer_type',actionId:'a',text:'SECRET INPUT',screenshot:'SECRET PNG',apiKey:'SECRET KEY'})
    const [line]=await received;const data=JSON.parse(line)
    assert.equal(data.tool,'computer_type');assert.doesNotMatch(line,/SECRET/)
    client.destroy()
  } finally { bridge.close() }
})

test('screenshots wait for hidden acknowledgement then restore visibility', async () => {
  const b=createCompanion({enabled:true,launch:false});await b.ready
  const client=net.createConnection(b.socketPath);client.setEncoding('utf8')
  try {
    await once(client,'connect')
    const initial=once(client,'data');client.write(JSON.stringify({type:'hello',token:b.token})+'\n');await initial
    let hidden=false,restored=false
    client.on('data',chunk=>{for(const line of chunk.trim().split('\n')){
      const value=JSON.parse(line)
      if(value.type==='visibility'&&!value.visible){hidden=true;client.write(JSON.stringify({type:'hidden',captureId:value.captureId})+'\n')}
      if(value.type==='visibility'&&value.visible)restored=true
    }})
    await b.withHidden(async()=>{assert.equal(hidden,true)})
    await new Promise(resolve=>setTimeout(resolve,10));assert.equal(restored,true)
  }finally{client.destroy();b.close()}
})

test('unknown element geometry is never guessed from a token',()=>{
  const snapshot={windowBounds:{x:100,y:200,width:800,height:600},screenshotWidth:800,screenshotHeight:600,entries:new Map([[1,{token:'token',x:null,y:null}]])}
  const target=presentationTarget({element:1,text:'private'},snapshot)
  assert.equal(target.point,null);assert.deepEqual(target.bounds,snapshot.windowBounds)
})

test('display-only control preserves deliberate hiding across captures',async()=>{
 const b=createCompanion({enabled:true,launch:false});await b.ready
 const renderer=net.createConnection(b.socketPath),control=net.createConnection(b.socketPath)
 renderer.setEncoding('utf8');control.setEncoding('utf8')
 try{
  await Promise.all([once(renderer,'connect'),once(control,'connect')])
  let next=once(renderer,'data');renderer.write(JSON.stringify({type:'hello',token:b.token})+'\n');await next
  next=once(control,'data');control.write(JSON.stringify({type:'hello',role:'control',token:b.token})+'\n');await next
  let lastVisibility
  renderer.on('data',chunk=>{for(const line of chunk.trim().split('\n')){const v=JSON.parse(line);if(v.type==='visibility'){lastVisibility=v.visible;if(v.captureId)renderer.write(JSON.stringify({type:'hidden',captureId:v.captureId})+'\n')}}})
  next=once(control,'data');control.write('{"type":"control","command":"hide"}\n');const [answer]=await next
  assert.equal(JSON.parse(answer).visible,false)
  await b.withHidden(async()=>{})
  await new Promise(resolve=>setTimeout(resolve,10));assert.equal(lastVisibility,false)
 }finally{renderer.destroy();control.destroy();b.close()}
})
