"""Pure animation and placement rules. No desktop access or input capability."""
import math
import random
from collections import OrderedDict

STATES={'idle','executing','approval','pending','confirmed','failed','cancelled','completed'}

def finite(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


def placement(target, display, monitors, width, height):
    monitor=monitors[0]
    corner=(monitor['x']+monitor['width']-width-24,monitor['y']+monitor['height']-height-24)
    # Mixed monitor coordinate spaces are deliberately not guessed in this MVP.
    if len(monitors)!=1 or not target or not display:
        return corner,None,'corner'
    mapping=display.get('mapping',{})
    if target.get('coordinateSpace')=='driver':
        if not all(finite(mapping.get(k)) for k in ('sx','sy','ox','oy')) or mapping['sx']<=0 or mapping['sy']<=0:
            return corner,None,'corner'
        sx,sy=1/mapping['sx'],1/mapping['sy'];ox,oy=mapping['ox'],mapping['oy']
    elif target.get('coordinateSpace')=='physical':
        dw,dh=display.get('width'),display.get('height')
        if not finite(dw) or not finite(dh) or dw<=0 or dh<=0:return corner,None,'corner'
        sx,sy=monitor['width']/dw,monitor['height']/dh;ox=oy=0
    else:return corner,None,'corner'
    if abs(sx-sy)>0.02*max(sx,sy):return corner,None,'corner'
    b=target.get('bounds',{})
    if not all(finite(b.get(k)) for k in ('x','y','width','height')) or b['width']<=0 or b['height']<=0:
        return corner,None,'corner'
    point=target.get('point')
    marker=None
    if point and finite(point.get('x')) and finite(point.get('y')):
        px,py=(point['x']-ox)*sx,(point['y']-oy)*sy
        if monitor['x']<=px<monitor['x']+monitor['width'] and monitor['y']<=py<monitor['y']+monitor['height']:
            marker=(px,py)
    if marker:
        x,y=marker[0]+36,marker[1]-height+30
        if x+width>monitor['x']+monitor['width']:x=marker[0]-width-36
    else:
        x,y=(b['x']+b['width']-ox)*sx+12,(b['y']-oy)*sy+24
        if x+width>monitor['x']+monitor['width']:x=(b['x']-ox)*sx-width-12
    x=min(max(x,monitor['x']),monitor['x']+monitor['width']-width)
    y=min(max(y,monitor['y']),monitor['y']+monitor['height']-height)
    # If clamping would cover the click point, move to the opposite vertical side.
    if marker and x-12<=marker[0]<=x+width+12 and y-12<=marker[1]<=y+height+12:
        return corner,marker,'corner-safe'
    return (round(x),round(y)),marker,'target' if marker else 'window'


class VariationSelector:
    """Rotate per operation; one action keeps its choice through foreground retry."""
    def __init__(self):self.counts={};self.remember=OrderedDict();self.bags={};self.last={}
    def choose(self,operation,action_id):
        key=(operation,str(action_id))
        if key in self.remember:return self.remember[key]
        if operation not in self.bags:self.bags[operation]=[0,1,2]
        if not self.bags[operation]:
            bag=[0,1,2];random.shuffle(bag)
            if bag[0]==self.last.get(operation):bag[0],bag[1]=bag[1],bag[0]
            self.bags[operation]=bag
        value=self.bags[operation].pop(0);self.last[operation]=value
        self.counts[operation]=self.counts.get(operation,0)+1
        self.remember[key]=value
        while len(self.remember)>64:self.remember.popitem(last=False)
        return value


class AnimationModel:
    def __init__(self,behavior):
        self.behavior=behavior;self.counters={};self.seq=-1;self.variants=VariationSelector()
        self.state='idle';self.tool='';self.clip='idle';self.caption='';self.target=None;self.display=None

    def event(self,event):
        if event.get('type')!='state' or not isinstance(event.get('seq'),int) or event['seq']<=self.seq:return False
        self.seq=event['seq'];self.state=event.get('state') if event.get('state') in STATES else 'idle'
        self.tool=event.get('tool','') if event.get('tool') in self.behavior['tools'] else ''
        key=self.tool if self.state=='executing' and self.tool else self.state
        entry=self.behavior['tools'].get(key) or self.behavior.get(key) or self.behavior['idle']
        count=self.variants.choose(key,event.get('actionId') or ('seq-'+str(self.seq)))
        self.clip=entry['clips'][count%len(entry['clips'])];self.caption=entry['copy'][count%len(entry['copy'])]
        self.target=event.get('target');self.display=event.get('display')
        return True


def hand_anchor(width,native=(286,250)):
    """Native full-character tap pose: hands stay attached to their original torso."""
    return width*native[0]/640,78+width*native[1]/640


def contact_placement(point,work,width,height,native=(286,250)):
    ax,ay=hand_anchor(width,native)
    return (round(min(max(point[0]-ax,work['x']),work['x']+work['width']-width)),
            round(min(max(point[1]-ay,work['y']),work['y']+work['height']-height)))


def resolve_clip(name,tool,state,age):
    # Sleeping is only for a genuinely long wait, never an instant 1s pause.
    return 'idle' if tool=='computer_wait' and state=='executing' and name=='sleep' and age<8 else name
