import gi,json,os,sys
from pathlib import Path
gi.require_version('Gtk','3.0')
from gi.repository import Gtk,Gdk,GLib
out=Path(sys.argv[1]);state={'pid':os.getpid(),'clicks':0,'mouse_buttons':[],'keys':[],'entry':'','scroll':0,'slider':20,'ready':False}
window=Gtk.Window(title='DSH Fish Verification Canvas');window.set_default_size(1300,850);window.set_decorated(False);window.move(120,120)
css=Gtk.CssProvider();css.load_from_data(b'''
window { background: #edf4fb; color: #20364f; }
.heading { font-size: 30px; font-weight: bold; }
.subtitle {font-size: 16px; color: #617a93;}
.card {background: #fff; border: 1px solid #d2e2f1; border-radius: 18px; padding: 20px;}
entry,button {font-size:18px; min-height:38px;}
button {background:#deedff; border:1px solid #b0cef0; border-radius:9px; color:#254e7b;}
''');Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(),css,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=18);box.set_border_width(32);window.add(box)
def label(text,style):
 x=Gtk.Label(label=text,xalign=0);x.get_style_context().add_class(style);return x
box.pack_start(label('大肥鱼 · 电脑操作伴随桌宠','heading'),False,False,0)
box.pack_start(label('专用验证窗口  /  真实截图、点击、按键、滚动与拖拽','subtitle'),False,False,0)
row=Gtk.Box(spacing=24);box.pack_start(row,True,True,0)
left=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=16);left.get_style_context().add_class('card');left.set_size_request(650,-1);row.pack_start(left,True,True,0)
left.pack_start(label('01  输入与点击','subtitle'),False,False,0)
entry=Gtk.Entry();entry.get_accessible().set_name('Verification input');entry.set_placeholder_text('等待鱼娘填入测试文字');left.pack_start(entry,False,False,0)
button=Gtk.Button(label='Verification Click · 点我计数');left.pack_start(button,False,False,0)
clicklabel=Gtk.Label(label='实际收到点击：0 次',xalign=0);left.pack_start(clicklabel,False,False,0)
def clicked(*_):state['clicks']+=1;clicklabel.set_text('实际收到点击：%s 次'%state['clicks'])
button.connect('clicked',clicked)
def mousepress(widget,event):
 if event.type==Gdk.EventType.BUTTON_PRESS:state['mouse_buttons'].append(event.button)
 return False
button.connect('button-press-event',mousepress)
left.pack_start(label('02  拖拽滑块','subtitle'),False,False,0)
slider=Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL,0,100,1);slider.set_value(20);slider.set_draw_value(True);slider.get_accessible().set_name('Verification slider');left.pack_start(slider,False,False,0)
left.pack_start(label('03  页面滚动','subtitle'),False,False,0)
scroll=Gtk.ScrolledWindow();scroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.ALWAYS);scroll.get_accessible().set_name('Verification scroll region');scroll.set_size_request(-1,200)
lines=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=18)
for i in range(30):lines.pack_start(Gtk.Label(label='测试内容  %02d    鱼娘只操作这个窗口。'%i,xalign=0),False,False,0)
scroll.add(lines);left.pack_start(scroll,True,True,0)
right=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=24);right.get_style_context().add_class('card');right.set_size_request(380,-1);row.pack_start(right,False,False,0)
for title,copy in [('动作跟随','鱼娘在目标旁边工作，身体避开点击位置。'),('状态清楚','正在做、等待批准、结果待确认，分别显示。'),('保持分寸','后台拒绝后先申请单次前台批准。'),('看结果再庆祝','发送了输入，不代表已经确认成功。')]:
 right.pack_start(label(title,'heading' if title=='动作跟随' else 'subtitle'),False,False,0)
 l=Gtk.Label(label=copy,xalign=0);l.set_line_wrap(True);l.set_max_width_chars(20);right.pack_start(l,False,False,0)
box.pack_start(label('本窗口不读取或修改你的文档，验证完成后自动关闭。','subtitle'),False,False,0)
def keypress(widget,event):state['keys'].append(Gdk.keyval_name(event.keyval));return False
window.connect('key-press-event',keypress);window.connect('destroy',Gtk.main_quit)
def rect(widget):
 point=widget.translate_coordinates(window,0,0);a=widget.get_allocation();return {'x':point[0],'y':point[1],'width':a.width,'height':a.height}
def save():
 state.update(entry=entry.get_text(),selection=list(entry.get_selection_bounds()),scroll=scroll.get_vadjustment().get_value(),slider=slider.get_value(),active=window.is_active(),ready=True,origin=list(window.get_position()),screen={'width':Gdk.Screen.get_default().get_width(),'height':Gdk.Screen.get_default().get_height()},width=window.get_allocated_width(),height=window.get_allocated_height(),rects={name:rect(w) for name,w in [('entry',entry),('button',button),('slider',slider),('scroll',scroll)]})
 tmp=out.with_suffix('.tmp');tmp.write_text(json.dumps(state));tmp.replace(out);return True
window.show_all();entry.grab_focus();GLib.timeout_add(100,save);Gtk.main()
