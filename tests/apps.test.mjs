import test from 'node:test';import assert from 'node:assert/strict';
import {listApps,launchApp} from '../lib/actions.js';
test('Linux app list excludes process-only kernel workers and retains minimized desktop apps',async()=>{
 const result=await listApps({platform:'linux',call:async tool=>tool==='list_apps'?{apps:[
  {name:'kworker/0:0',pid:1,running:true},{name:'Editor',pid:2,running:true},
  {name:'Minimized',pid:3,running:true,kind:'desktop'},
 ]}:{windows:[{pid:2,app_name:'Editor'}]}});
 assert.deepEqual(result.apps.map(a=>a.name),['Editor','Minimized']);
});
test('launch handoff timeout recovers confirmed running app without a second launch',async()=>{
 let launches=0;
 const result=await launchApp({name:'editor'},{delay:async()=>{},call:async tool=>{
  if(tool==='launch_app'){launches++;const e=Error('handoff');e.driverResult={code:'launch_handoff_timeout'};throw e;}
  return tool==='list_apps'?{apps:[{name:'Editor',launch_path:'/usr/bin/editor',pid:42,running:true}]}:{windows:[{pid:42,is_on_screen:true}]};
 }});
 assert.equal(launches,1);assert.equal(result.ok,true);assert.equal(result.pid,42);
 assert.match(result.result,/窗口可见/);
});
test('requesting a new instance never mistakes an old window for the new launch',async()=>{
 let calls=0;const e=Error('handoff');e.driverResult={code:'launch_handoff_timeout'};
 await assert.rejects(launchApp({name:'editor',creates_new_instance:true},{call:async()=>{calls++;throw e}}),/handoff/);
 assert.equal(calls,1);
});
