#!/usr/bin/env python3
"""Actual renderer preview for observation, typing and state feedback."""
import argparse,time,json
from pathlib import Path
import cairo
from preview_rich import make_pet,label
CASES=[('screen_observe',0,'举望远镜查看'),('screen_zoom',0,'举放大镜细看'),('computer_type',0,'双手敲键盘'),('computer_type',2,'拿小本记录'),('computer_wait',2,'久等后小憩'),('app_launch',1,'转身招手迎接')]
def main():
 parser=argparse.ArgumentParser();parser.add_argument('directory');args=parser.parse_args();out=Path(args.directory);out.mkdir(parents=True,exist_ok=True);began=time.monotonic();pets=[]
 for tool,v,title in CASES:
  p=make_pet(tool,v);p.model.clip=p.model.behavior['tools'][tool]['clips'][v];p.model.caption=title;p.last_event-=9 if tool=='computer_wait' else 0;p.window.position=(120,70);p.select_clip();pets.append(p)
 for i in range(60):
  surface=cairo.ImageSurface(cairo.FORMAT_ARGB32,1800,800);root=cairo.Context(surface);root.set_source_rgb(.94,.97,1);root.paint()
  for j,(p,(_,_,title)) in enumerate(zip(pets,CASES)):
   cr=cairo.Context(surface);cr.translate(j%3*600,j//3*400);label(cr,title,18,15,20)
   if p.iterator:p.iterator.advance(None)
   layer=cairo.ImageSurface(cairo.FORMAT_ARGB32,360,287);p.draw(None,cairo.Context(layer));cr.set_source_surface(layer,120,70);cr.paint()
  label(root,'实际渲染器预览 · 原角色完整素材与新姿势组合',18,774,13);surface.write_to_png(str(out/f'{i:04}.png'));time.sleep(max(0,(i+1)/15-(time.monotonic()-began)))
if __name__=='__main__':main()
