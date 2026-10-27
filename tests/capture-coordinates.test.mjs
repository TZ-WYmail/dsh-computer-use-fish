import test from 'node:test';import assert from 'node:assert/strict';
import {windowScale,windowLocalOf} from '../lib/human.js';
import {presentationTarget} from '../lib/companion.js';

test('HiDPI plus capture downsampling uses original dimensions, not reduced frame width',()=>{
 const snap={screenshotWidth:1326,screenshotHeight:867,originalScreenshotWidth:2600,windowBounds:{x:120,y:120,width:1300,height:850}};
 assert.equal(windowScale(snap),2);
 assert.deepEqual(windowLocalOf(456,288,snap),{x:228,y:144});
 const target=presentationTarget({x:456,y:288},snap);
 assert.equal(target.coordinateSpace,'driver');
 assert.ok(Math.abs(target.point.x-(120+456/1326*1300))<.001);
});
test('downsampling alone is left for the driver to restore',()=>{
 const snap={screenshotWidth:1326,originalScreenshotWidth:2600,windowBounds:{width:2600}};
 assert.equal(windowScale(snap),1);assert.deepEqual(windowLocalOf(456,288,snap),{x:456,y:288});
});
