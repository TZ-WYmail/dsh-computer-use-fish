#!/usr/bin/env python3
"""Click-through GTK/XWayland companion. Receives presentation metadata only."""
import argparse,json,os,socket,threading,time,signal,math
from collections import OrderedDict
from pathlib import Path
import gi,cairo

gi.require_version('PangoCairo','1.0');gi.require_version('Gtk','3.0');gi.require_version('Gdk','3.0');gi.require_version('GdkPixbuf','2.0')
from gi.repository import Gtk,Gdk,GdkPixbuf,GLib,Pango,PangoCairo
from model import AnimationModel,placement,hand_anchor,contact_placement,resolve_clip
from motion import GestureMotion

BASE=Path(__file__).resolve().parent
POSES=json.loads((BASE/'assets/poses.json').read_text())
LABELS={'idle':'休息中','executing':'正在操作','approval':'等待批准','pending':'结果待确认','confirmed':'已确认完成','failed':'这一步未完成','cancelled':'已停止','completed':'查看完毕'}

class Pet:
    def __init__(self,args):
        self.args=args;self.width=args.size;self.height=round(args.size*180/320)+84
        self.model=AnimationModel(json.loads((BASE/'behavior.json').read_text()))
        self.cache=OrderedDict();self.iterator=None;self.last_event=time.monotonic();self.capture_hidden=False
        self.sock=None;self.position_mode='corner';self.marker_point=None;self.motion=None;self.motion_frame=None;self.motion_history=[];self.last_clip=None
        self.window=self.make_window('DSH Fat Fish Companion',self.width,self.height)
        self.area=Gtk.DrawingArea();self.window.add(self.area);self.area.connect('draw',self.draw)
        self.marker=self.make_window('DSH Fat Fish Target',180,180)
        marker_area=Gtk.DrawingArea();self.marker.add(marker_area);marker_area.connect('draw',self.draw_marker)
        self.window.show_all();self.pass_through(self.window);self.marker.hide()
        self.receive({'type':'state','state':'idle','seq':0})
        GLib.timeout_add(250 if args.reduced_motion else 25,self.tick)
        GLib.timeout_add(120,self.connect_events)
        self.window.connect('destroy',lambda *_:Gtk.main_quit())
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT,signal.SIGTERM,self.quit)

    def make_window(self,title,width,height):
        w=Gtk.Window(type=Gtk.WindowType.TOPLEVEL);w.set_title(title)
        w.set_wmclass('dsh-fat-fish','DshFatFish');w.set_default_size(width,height)
        w.set_resizable(False);w.set_decorated(False);w.set_app_paintable(True)
        w.set_keep_above(True);w.set_skip_taskbar_hint(True);w.set_skip_pager_hint(True)
        w.set_accept_focus(False);w.set_focus_on_map(False);w.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        visual=w.get_screen().get_rgba_visual()
        if visual:w.set_visual(visual)
        w.connect('realize',lambda widget:self.pass_through(widget))
        return w

    def pass_through(self,window):
        if window.get_window():window.get_window().input_shape_combine_region(cairo.Region(),0,0)

    def quit(self):
        self.marker.destroy();self.window.destroy();return False

    def connect_events(self):
        x,y=self.window.get_position();w,h=self.window.get_size()
        self.hello_geometry={'x':x,'y':y,'width':w,'height':h}
        threading.Thread(target=self.read_events,daemon=True).start()
        return False

    def read_events(self):
        try:
            self.sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);self.sock.connect(self.args.socket)
            self.sock.sendall((json.dumps({'type':'hello','token':os.environ.pop('DSH_FISH_TOKEN',''),'geometry':self.hello_geometry})+'\n').encode())
            with self.sock.makefile('r',encoding='utf-8') as stream:
                while True:
                    line=stream.readline(8193)
                    if not line or len(line)>8192:break
                    try:event=json.loads(line)
                    except ValueError:break
                    GLib.idle_add(self.receive,event)
        except (OSError,ValueError):pass
        GLib.idle_add(self.quit)

    def receive(self,event):
        if event.get('type')=='gesture':
            motion_id=event.get('motionId')
            if event.get('phase')=='approach':
                if self.capture_hidden:return False
                destination=event.get('target')
                if not isinstance(destination,dict):return False
                target=dict(destination)
                if event.get('tool')=='computer_drag' and target.get('fromPoint'):target['point']=target['fromPoint']
                variant=self.model.variants.choose(event['tool'],event.get('actionId') or motion_id)
                style=self.model.behavior.get('gestures',{}).get(event['tool'],[{}, {}, {}])[variant]
                end,point,mode=self.motion_placement(target,event.get('display'),style)
                if mode=='corner':return False
                final,tip,_=self.motion_placement(destination,event.get('display'),style)
                event={**event,'variant':variant,'style':style,'workTop':self.monitors()[0]['y']}
                self.motion=GestureMotion(event,self.window.get_position(),end,point,time.monotonic(),self.args.reduced_motion,(final,tip or point))
                self.motion_frame=None;self.position_mode=mode
                self.motion_history.append({'motionId':motion_id,'phase':'approach','at':time.monotonic()})
                self.motion_history=self.motion_history[-32:]
            elif self.motion and self.motion.id==motion_id:
                phase=event.get('phase');self.motion_history.append({'motionId':motion_id,'phase':phase,'at':time.monotonic()})
                self.motion_history=self.motion_history[-32:]
                if phase=='dispatch':self.motion.dispatch(time.monotonic())
                elif phase=='settle':self.motion.settle(time.monotonic())
                elif phase=='cancel':self.motion=None;self.motion_frame=None;self.marker.hide();self.select_clip()
            self.diagnostics();return False
        if event.get('type')=='visibility':
            self.capture_hidden=not event.get('visible',True)
            if self.capture_hidden:
                self.motion=None;self.motion_frame=None
                self.window.hide();self.marker.hide();self.window.get_display().flush()
                capture_id=event.get('captureId')
                def acknowledge():
                    try:self.sock.sendall((json.dumps({'type':'hidden','captureId':capture_id})+'\n').encode())
                    except OSError:pass
                    return False
                GLib.timeout_add(60,acknowledge)
            else:
                self.window.show_all();self.pass_through(self.window);self.reposition()
            return False
        if not self.model.event(event):return False
        self.last_event=time.monotonic()
        if self.model.state in ('approval','failed','cancelled','idle'):
            self.motion=None;self.motion_frame=None
        self.select_clip()
        pointer=self.model.tool in ('computer_click','computer_double_click','computer_right_click','computer_scroll','computer_drag')
        if not self.motion and not (pointer and self.model.state=='executing'):self.reposition()
        self.area.queue_draw();GLib.timeout_add(100,self.diagnostics)
        return False

    def select_clip(self,name=None):
        name=name or self.model.clip
        name=resolve_clip(name,self.model.tool,self.model.state,time.monotonic()-self.last_event)
        if name==self.last_clip:return
        self.last_clip=name;self.clip_wall=time.time()
        if name not in self.cache:
            try:
                file=POSES[name[5:]]['file'] if name.startswith('pose:') else name+'.gif'
                self.cache[name]=GdkPixbuf.PixbufAnimation.new_from_file(str(BASE/'assets'/file))
            except GLib.Error:self.cache[name]=GdkPixbuf.PixbufAnimation.new_from_file(str(BASE/'assets/idle.gif'))
            while len(self.cache)>2:self.cache.popitem(last=False)
        self.cache.move_to_end(name);self.iterator=self.cache[name].get_iter(None)

    def monitors(self):
        display=self.window.get_display();out=[]
        for i in range(display.get_n_monitors()):
            g=display.get_monitor(i).get_workarea()
            out.append({'x':g.x,'y':g.y,'width':g.width,'height':g.height})
        return out

    def motion_placement(self,target,display,style=None):
        monitors=[];screen=self.window.get_display()
        for i in range(screen.get_n_monitors()):
            g=screen.get_monitor(i).get_geometry();monitors.append({'x':g.x,'y':g.y,'width':g.width,'height':g.height})
        pos,point,mode=placement(target,display,monitors,self.width,self.height)
        if point:
            work=self.monitors()[0];px,py=point
            pos=contact_placement(point,work,self.width,self.height,(style or {}).get('anchor',(286,250)))
        return pos,point,mode

    def reposition(self):
        monitors=self.monitors()
        # Transform driver display pixels with full monitor geometry, then clamp to work area.
        transforms=[]
        display=self.window.get_display()
        for i in range(display.get_n_monitors()):
            g=display.get_monitor(i).get_geometry();transforms.append({'x':g.x,'y':g.y,'width':g.width,'height':g.height})
        pos,marker,mode=placement(self.model.target,self.model.display,transforms,self.width,self.height)
        work=monitors[0];x=min(max(pos[0],work['x']),work['x']+work['width']-self.width);y=min(max(pos[1],work['y']),work['y']+work['height']-self.height)
        self.position_mode=mode;self.window.move(int(x),int(y));self.marker_point=marker
        if marker and self.model.state in ('executing','pending') and not self.capture_hidden:
            self.marker.move(round(marker[0]-90),round(marker[1]-90));self.marker.show_all();self.pass_through(self.marker)
        else:self.marker.hide()

    def diagnostics(self):
        if not self.args.diagnostics:return
        state={'pid':os.getpid(),'state':self.model.state,'tool':self.model.tool,'clip':self.model.clip,'mode':self.position_mode,'position':list(self.window.get_position()),'marker':self.marker_point,'click_through':True,'accept_focus':self.window.get_accept_focus(),'visible':not self.capture_hidden,'seq':self.model.seq,'motion':self.motion_frame,'history':self.motion_history}
        Path(self.args.diagnostics).write_text(json.dumps(state));return False

    def tick(self):
        now=time.monotonic();age=now-self.last_event
        if self.motion and not self.capture_hidden:
            frame=self.motion.frame(now);self.motion_frame=frame
            self.window.move(*frame['position']);self.marker_point=frame['point']
            if frame['point']:
                self.marker.move(round(frame['point'][0]-90),round(frame['point'][1]-90));self.marker.show_all();self.pass_through(self.marker)
            else:self.marker.hide()
            pose=frame.get('pose')
            clip=('pose:'+pose if pose in POSES else pose) if pose else 'run' if frame['phase']=='run' else self.motion.style.get('clip','tap')
            self.select_clip(clip)
            if frame['ready']:
                self.motion.ack=True
                self.motion_history.append({'motionId':self.motion.id,'phase':'ready','at':now})
                try:self.sock.sendall((json.dumps({'type':'gesture_ready','motionId':self.motion.id})+'\n').encode())
                except OSError:pass
                self.diagnostics()
            self.marker.queue_draw();self.area.queue_draw()
            if frame['phase']=='done':
                self.motion=None;self.motion_frame=None;self.marker.hide();self.select_clip();self.reposition();self.diagnostics()
        if self.model.state not in ('idle','approval','executing') and age>5:
            pending=self.model.state=='pending'
            remote_seq=self.model.seq
            self.model.event({'type':'state','state':'idle','seq':remote_seq+1})
            self.model.seq=remote_seq
            if pending:self.model.caption='上一步还待确认，先回角落等。'
            self.select_clip();self.reposition();self.diagnostics()
        if self.model.tool=='computer_wait' and self.model.state=='executing' and age>=8 and self.model.clip=='sleep':self.select_clip()
        if not self.capture_hidden:
            if self.model.state=='executing':self.area.queue_draw()
            if self.iterator and not self.args.reduced_motion:
                stamp=None
                if self.motion_frame and ((self.last_clip=='spin' and self.motion_frame['phase']=='windup') or self.last_clip=='tail'):
                    offset=self.motion_frame['windup_progress']*5 if self.last_clip=='spin' else (time.monotonic()-self.motion.contact)*4 if self.motion.contact is not None else self.motion_frame['windup_progress']
                    virtual=self.clip_wall+max(0,offset);stamp=GLib.TimeVal();stamp.tv_sec=int(virtual);stamp.tv_usec=int((virtual-int(virtual))*1000000)
                if self.iterator.advance(stamp):self.area.queue_draw()
            if self.model.state=='idle' and age>15:return True
        return True

    @staticmethod
    def clear(cr):
        cr.set_operator(cairo.OPERATOR_SOURCE);cr.set_source_rgba(0,0,0,0);cr.paint();cr.set_operator(cairo.OPERATOR_OVER)

    def draw(self,widget,cr):
        self.clear(cr)
        width=self.width
        cr.new_sub_path();cr.arc(width-15,15,13,-1.57,0);cr.arc(width-15,58,13,0,1.57);cr.arc(15,58,13,1.57,3.14);cr.arc(15,15,13,3.14,4.71);cr.close_path()
        cr.set_source_rgba(.97,.99,1,.96);cr.fill_preserve();cr.set_source_rgba(.32,.55,.81,.8);cr.set_line_width(1.2);cr.stroke()
        layout=PangoCairo.create_layout(cr);layout.set_font_description(Pango.FontDescription('Sans 10'));layout.set_text('跳起来啦' if self.motion_frame and self.motion_frame['phase']=='jump' else '正在奔跑' if self.motion_frame and self.motion_frame['phase']=='run' else LABELS.get(self.model.state,'休息中'),-1)
        cr.set_source_rgb(.22,.40,.65);cr.move_to(15,10);PangoCairo.show_layout(cr,layout)
        layout.set_font_description(Pango.FontDescription('Sans 11'));layout.set_width((width-30)*Pango.SCALE);layout.set_wrap(Pango.WrapMode.WORD_CHAR);layout.set_text(('嘿——跳起来拍！' if self.motion_frame['phase']=='jump' else '蹲一下，准备起跳～' if self.motion_frame['phase']=='crouch' else '让让，鱼鱼跑过去！' if self.motion_frame['phase']=='run' else self.motion.style.get('name','抬手')+'，瞄准这里～' if self.motion_frame['phase'] in ('armed','windup') else self.motion.style.get('copy','拍！再看看结果。')) if self.motion_frame else self.model.caption,-1)
        cr.set_source_rgb(.17,.22,.32);cr.move_to(15,31);PangoCairo.show_layout(cr,layout)
        if self.iterator:
            frame=self.iterator.get_pixbuf()
            motion=self.motion_frame
            custom=POSES.get(self.last_clip[5:]) if self.last_clip and self.last_clip.startswith('pose:') else None
            if not custom and self.last_clip!='spin' and motion and motion['phase']!='run' and self.motion and self.motion.tool in ('computer_click','computer_double_click','computer_right_click'):
                pose='ready' if motion['phase'] in ('windup','armed','crouch','jump') else 'contact' if motion['impact']>.15 else 'recover'
                if not hasattr(self,'poses'):self.poses={}
                if pose not in self.poses:self.poses[pose]=GdkPixbuf.Pixbuf.new_from_file(str(BASE/'assets'/('tap-'+pose+'.png')))
                frame=self.poses[pose]
            cr.save()
            motion=self.motion_frame
            if custom:
                self.transform_custom(cr,custom,motion)
            elif motion and motion['phase']!='run':
                native=self.motion.style.get('anchor',(286,250));ax,ay=hand_anchor(width,native);cr.translate(ax,ay)
                cr.translate(*motion.get('body_offset',(0,0)));cr.rotate(motion.get('tilt',0))
                cr.scale(-1 if motion.get('mirror') else 1,1)
                if motion.get('crouch',0)>0:
                    footx=(320-286)*width/640;footy=(332-250)*width/640
                    cr.translate(footx,footy);cr.scale(1+.10*motion['crouch'],1-.22*motion['crouch']);cr.translate(-footx,-footy)
                impulse=motion['impact'];cr.rotate(-self.motion.style.get('lean',.035) if motion['phase'] in ('windup','armed') else self.motion.style.get('lean',.045)*impulse)
                press=self.motion.style.get('press',.035);cr.scale(1+press*.6*impulse,1-press*impulse)
                cr.scale(width/frame.get_width(),width/frame.get_width());cr.translate(-native[0],-native[1])
            else:
                cr.translate(width/2,78+width*360/640/2)
                if motion:
                    cr.translate(0,-motion['bob']);cr.rotate(.08*motion['direction'])
                    if motion['direction']>0:cr.scale(-1,1)
                elif self.model.state=='executing' and not self.args.reduced_motion:
                    age=time.monotonic()-self.last_event
                    cr.rotate(math.sin(age*3)*.035)
                cr.scale(width/frame.get_width(),width/frame.get_width());cr.translate(-frame.get_width()/2,-frame.get_height()/2)
            Gdk.cairo_set_source_pixbuf(cr,frame,0,0);cr.paint();cr.restore()
        return False

    def transform_custom(self,cr,meta,motion):
        width=self.width;l,t,r,b=meta['bbox'];base=width/640*meta.get('bodyHeight',270)/(b-t)
        if motion:
            ax,ay=hand_anchor(width);px,py=meta['anchor'];mirror=motion.get('mirror',False)
            left,right=(r-px,px-l) if mirror else (px-l,r-px)
            limits=[base]
            for extent,space in ((left,ax-4),(right,width-ax-4),(py-t,ay-78),(b-py,self.height-ay-3)):
                if extent>0:limits.append(max(1,space)/extent)
            scale=min(limits);cr.translate(ax,ay);cr.translate(*motion.get('body_offset',(0,0)))
            tilt=motion.get('tilt',0)
            if motion['phase']=='windup':tilt+=self.motion.style.get('lean',.04)
            cr.rotate(tilt);cr.scale((-1 if mirror else 1)*motion.get('yaw',1),1)
            press=self.motion.style.get('press',.04)*motion['impact'];cr.scale(1+press*.4,1-press)
        else:
            px,py=(l+r)/2,b;scale=base;cr.translate(width/2,78+width*335/640)
            if self.model.state=='executing' and not getattr(self.args,'reduced_motion',False):
                age=time.monotonic()-self.last_event;cr.translate(0,math.sin(age*3)*2);cr.rotate(math.sin(age*2)*.025)
        cr.scale(scale,scale);cr.translate(-px,-py)

    def draw_marker(self,widget,cr):
        self.clear(cr);frame=self.motion_frame
        # Only a small contact cue. All anatomy comes from the full-character artwork.
        if not frame:
            cr.set_source_rgba(.18,.64,1,.4);cr.set_line_width(1);cr.arc(90,90,5,0,math.tau);cr.stroke();return False
        if frame.get('jump_style') and frame['phase'] in ('crouch','jump'):
            fade=1-.5*min(1,frame.get('lift',0)/84);cr.save();cr.translate(106,128);cr.scale(18*fade,4*fade)
            cr.set_source_rgba(.22,.36,.55,.18);cr.arc(0,0,1,0,math.tau);cr.fill();cr.restore()
        if frame['phase']!='contact' or frame['impact']<=0:return False
        strength=frame['impact'];cr.set_source_rgba(1,.72,.28,strength*.75);cr.set_line_width(1.5)
        cr.arc(90,90,6+(1-strength)*8,0,math.tau);cr.stroke()
        return False


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--socket',required=True);parser.add_argument('--size',type=int,default=300);parser.add_argument('--reduced-motion',action='store_true');parser.add_argument('--diagnostics')
    args=parser.parse_args();args.size=max(200,min(args.size,420));GLib.set_prgname('dsh-fat-fish');Gtk.init([]);Pet(args);Gtk.main()

if __name__=='__main__':main()
