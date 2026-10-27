#!/usr/bin/env python3
"""Render an isolated animation preview using the production drawing functions."""
import os,sys,time,json,argparse,math
from types import SimpleNamespace
from pathlib import Path
from collections import OrderedDict
import cairo
from pet import Pet,GdkPixbuf,Pango,PangoCairo
from model import AnimationModel,contact_placement
from motion import GestureMotion
class Window:
    position=(40,240)
    def get_position(self):return self.position

def label(cr,text,x,y,size=16,color=(.15,.27,.42)):
    layout=PangoCairo.create_layout(cr);layout.set_font_description(Pango.FontDescription('Sans '+str(size)));layout.set_text(text,-1)
    cr.set_source_rgb(*color);cr.move_to(x,y);PangoCairo.show_layout(cr,layout)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('directory');parser.add_argument('--variant',type=int,default=0);parser.add_argument('--tool',default='computer_double_click');args=parser.parse_args();out=Path(args.directory);out.mkdir(parents=True,exist_ok=True)
    pet=Pet.__new__(Pet);pet.args=SimpleNamespace(reduced_motion=False);pet.width=300;pet.height=253;pet.window=Window();pet.cache=OrderedDict();pet.iterator=None;pet.last_clip=None;pet.motion=None;pet.motion_frame=None;pet.marker_point=None
    pet.model=AnimationModel(json.loads((Path(__file__).parent/'behavior.json').read_text()));pet.model.caption='出发，去帮你点一下！';pet.model.state='executing';pet.model.clip='idle'
    begun=time.monotonic();motion=None;contact_at=None;settled=False
    for i in range(75):
        now=time.monotonic();age=now-begun
        if age>.4 and motion is None:
            end=contact_placement((560,294),{'x':0,'y':0,'width':900,'height':560},300,253)
            style=pet.model.behavior.get('gestures',{}).get(args.tool,[{}, {}, {}])[args.variant%3]
            motion=GestureMotion({'motionId':'preview-2','tool':args.tool,'count':2 if args.tool=='computer_double_click' else 1,'variant':args.variant,'style':style},(40,240),end,(560,294),now)
        if motion:
            frame=motion.frame(now)
            if frame['ready']:
                motion.ack=True;motion.dispatch(now);contact_at=now
            if contact_at and now-contact_at>.45 and not settled:motion.settle(now);settled=True
            frame=motion.frame(now);pet.window.position=frame['position'];pet.marker_point=frame['point'];pet.motion=motion;pet.motion_frame=frame
            if frame['phase']=='done':
                pet.motion_frame=None;pet.model.state='pending';pet.model.caption='已经拍了，看看结果～';pet.select_clip('look')
            else:
                pose=frame.get('pose');pet.select_clip(('pose:'+pose if pose in __import__('pet').POSES else pose) if pose else 'run' if frame['phase']=='run' else motion.style.get('clip','tap'))
        else:pet.select_clip('idle')
        if pet.iterator:pet.iterator.advance(None)
        canvas=cairo.ImageSurface(cairo.FORMAT_ARGB32,900,560);cr=cairo.Context(canvas);cr.set_source_rgb(.93,.96,1);cr.paint()
        label(cr,pet.model.behavior['tools'][args.tool]['variants'][args.variant%3],32,25,24);label(cr,'使用实际桌宠渲染器的动画预览',34,67,12)
        cr.set_source_rgb(.68,.83,1);cr.rectangle(475,270,170,50);cr.fill();label(cr,'操作目标',507,282,17)
        for width,height,pos,draw in [(300,253,pet.window.position,pet.draw),(180,180,(470,204),pet.draw_marker)]:
            if draw==pet.draw_marker and not pet.motion_frame:continue
            layer=cairo.ImageSurface(cairo.FORMAT_ARGB32,width,height);draw(None,cairo.Context(layer));cr.set_source_surface(layer,*pos);cr.paint()
        label(cr,'角色以自身双手拍击目标，动作与身体保持一体。',32,515,13)
        canvas.write_to_png(str(out/f'{i:04}.png'))
        time.sleep(max(0,(i+1)/15-(time.monotonic()-begun)))
if __name__=='__main__':main()
