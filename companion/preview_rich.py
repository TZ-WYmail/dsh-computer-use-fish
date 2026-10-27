#!/usr/bin/env python3
"""Six production-rendered choreographies on isolated preview stages. No desktop input."""
import json,time,argparse
from pathlib import Path
from collections import OrderedDict
from types import SimpleNamespace
import cairo
from pet import Pet,POSES,GLib
from preview_gesture import Window,label
from model import AnimationModel,contact_placement
from motion import GestureMotion
BASE=Path(__file__).parent
CASES=[('computer_click',1),('computer_double_click',0),('computer_drag',0),('computer_drag',1),('computer_drag',2),('computer_scroll',0)]
def make_pet(tool,variant):
 p=Pet.__new__(Pet);p.args=SimpleNamespace(reduced_motion=False);p.width=360;p.height=287;p.window=Window();p.window.position=(30,70);p.cache=OrderedDict();p.iterator=None;p.last_clip=None;p.motion=None;p.motion_frame=None;p.marker_point=None
 p.model=AnimationModel(json.loads((BASE/'behavior.json').read_text()));p.model.state='executing';p.model.tool=tool;p.model.caption='准备操作';p.model.clip='idle';p.last_event=time.monotonic()
 return p

def main():
 parser=argparse.ArgumentParser();parser.add_argument('directory');args=parser.parse_args();out=Path(args.directory);out.mkdir(parents=True,exist_ok=True)
 pets=[make_pet(*case) for case in CASES];began=time.monotonic();contacts={};settled=set()
 for i in range(84):
  now=time.monotonic();age=now-began;canvas=cairo.ImageSurface(cairo.FORMAT_ARGB32,1800,800);root=cairo.Context(canvas);root.set_source_rgb(.94,.97,1);root.paint()
  for j,(p,(tool,variant)) in enumerate(zip(pets,CASES)):
   cr=cairo.Context(canvas);cr.translate((j%3)*600,(j//3)*400);style=p.model.behavior['gestures'][tool][variant]
   startpoint=(200,265) if tool=='computer_drag' else (400,265);end=contact_placement(startpoint,{'x':0,'y':0,'width':600,'height':400},360,287);finish=contact_placement((400,265),{'x':0,'y':0,'width':600,'height':400},360,287)
   if age>.3 and p.motion is None:p.motion=GestureMotion({'motionId':str(j),'tool':tool,'variant':variant,'style':style,'durationMs':1000,'direction':'down'},(30,70),end,startpoint,now,finish=(finish,(400,265)))
   if p.motion:
    frame=p.motion.frame(now)
    if frame['ready']:p.motion.ack=True;p.motion.dispatch(now);contacts[j]=now
    if j in contacts and now-contacts[j]>(1 if tool=='computer_drag' else .85) and j not in settled:p.motion.settle(now);settled.add(j)
    frame=p.motion.frame(now);p.motion_frame=frame;p.window.position=frame['position'];p.marker_point=frame['point']
    if frame['phase']=='done':p.motion_frame=None;p.model.state='pending';p.model.caption='结果待确认';p.select_clip('look')
    else:
     pose=frame.get('pose');p.select_clip(('pose:'+pose if pose in POSES else pose) if pose else 'run' if frame['phase']=='run' else style.get('clip','tap'))
   else:p.select_clip('idle')
   if p.iterator:
    stamp=None
    if p.motion_frame and p.last_clip=='spin' and p.motion_frame['phase']=='windup':
     virtual=p.clip_wall+p.motion_frame['windup_progress']*5;stamp=GLib.TimeVal();stamp.tv_sec=int(virtual);stamp.tv_usec=int(virtual%1*1000000)
    p.iterator.advance(stamp)
   label(cr,style['name'],18,12,20);cr.set_source_rgb(.75,.85,.98)
   if tool=='computer_drag':
    cr.rectangle(178,250,44,38);cr.fill();label(cr,'起点',178,295,11);cr.rectangle(378,250,44,38);cr.stroke();label(cr,'终点',378,295,11)
   else:cr.rectangle(340,248,120,40);cr.fill();label(cr,'操作区域',348,300,11)
   for w,h,pos,draw in [(360,287,p.window.position,p.draw),(180,180,(p.marker_point[0]-90,p.marker_point[1]-90) if p.marker_point else (0,0),p.draw_marker)]:
    if draw==p.draw_marker and not p.motion_frame:continue
    layer=cairo.ImageSurface(cairo.FORMAT_ARGB32,w,h);draw(None,cairo.Context(layer));cr.set_source_surface(layer,*pos);cr.paint()
  label(root,'实际渲染器动画预览 · 仅演示人物动作，未向桌面发送点击',18,774,13)
  canvas.write_to_png(str(out/f'{i:04}.png'));time.sleep(max(0,(i+1)/15-(time.monotonic()-began)))
if __name__=='__main__':main()
