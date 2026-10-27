"""Deterministic full-body choreography. This module cannot execute desktop input."""
import math

class GestureMotion:
    def __init__(self,event,start,end,point,now,reduced=False,finish=None):
        self.id=event['motionId'];self.tool=event['tool'];self.start=start;self.end=end;self.point=point
        self.finish=finish or (end,point);self.started=now;self.contact=None;self.until=None;self.ack=False;self.reduced=reduced
        self.count=2 if self.tool=='computer_double_click' else max(1,min(3,event.get('count',1)))
        self.variant=int(event.get('variant',0))%3;self.style=event.get('style',{});self.kind=self.style.get('kind','tap')
        self.direction=1 if end[0]>=start[0] else -1
        self.travel=0 if reduced else min(.85,max(.45,math.dist(start,end)/1300))
        self.jump=self.kind in ('jump_slap','jump_double') and not reduced
        self.crouch=self.style.get('crouchSeconds',.16);self.flight=self.style.get('flightSeconds',.64)
        self.height=min(self.style.get('jumpHeight',84),max(0,end[1]-event.get('workTop',0)))
        if self.height<16:self.jump=False
        self.windup=.04 if reduced else self.crouch+self.flight if self.jump else .16 if self.kind in ('jump_slap','jump_double') else self.style.get('windup',.22)
        self.drag_seconds=max(.15,min(1.5,event.get('durationMs',500)/1000))
        self.scroll_direction=event.get('direction','down')
    def dispatch(self,now):self.contact=now
    def settle(self,now):
        hold=.75 if self.tool=='computer_scroll' else .22
        self.until=max(now+.22,(self.contact if self.contact is not None else now)+max(hold,.16*self.count+.2))
    def frame(self,now):
        elapsed=max(0,now-self.started);progress=min(1,elapsed/self.travel) if self.travel else 1
        t=progress*progress*(3-2*progress)
        x=self.start[0]+(self.end[0]-self.start[0])*t;y=self.start[1]+(self.end[1]-self.start[1])*t
        phase='run' if progress<1 else 'windup' if elapsed<self.travel+self.windup else 'armed'
        point=self.point;impact=0;hand=0;lift=0;crouch=0;air=0;beat_index=0;pose=self.style.get('pose');mirror=False;yaw=1.;tilt=0.;body_offset=(0,0)
        u=min(1,max(0,(elapsed-self.travel)/self.windup))
        if self.jump and progress>=1 and self.contact is None:
            local=elapsed-self.travel
            if local<self.crouch:phase='crouch';crouch=max(0,min(1,local/self.crouch))
            elif local<self.windup:phase='jump';air=(local-self.crouch)/self.flight;lift=4*air*(1-air)*self.height;y-=lift
        elif self.kind in ('turn_slap','turn_double') and phase=='windup' and not self.reduced:
            pose=None;yaw=1.;mirror=False
        elif self.kind=='crouch_tap' and phase=='windup' and not self.reduced:
            crouch=math.sin(u*math.pi)*.8
        elif self.kind=='rush_tap' and phase=='windup' and not self.reduced:
            x-=self.direction*28*(1-u);tilt=.18*self.direction*(1-u)
        if phase=='run':pose=None
        if phase=='run' and not self.reduced:
            if self.variant==1:lift=abs(math.sin(progress*math.pi*3))*18;y-=lift
            elif self.variant==2:pose='glide'
        if self.contact is not None:
            age=max(0,now-self.contact);phase='contact';beat=age/.16;beat_index=min(self.count-1,int(beat+1e-8))
            if beat<self.count:impact=max(0,1-(beat%1)*1.5)
            hand=1
            if self.tool in ('computer_click','computer_double_click','computer_right_click'):
                hand=1-.65*math.sin((beat%1)*math.pi) if beat<self.count else .25
            if self.kind=='alternate_double':pose='tap-left' if beat_index%2==0 else 'tap-right';mirror=beat_index%2==1
            elif self.kind in ('turn_slap','turn_double'):pose='turn-slap'
            if self.tool=='computer_drag' and self.point and self.finish[1]:
                fraction=min(1,age/self.drag_seconds);end,tip=self.finish
                x=self.end[0]+(end[0]-self.end[0])*fraction;y=self.end[1]+(end[1]-self.end[1])*fraction
                point=(self.point[0]+(tip[0]-self.point[0])*fraction,self.point[1]+(tip[1]-self.point[1])*fraction)
                dx=end[0]-self.end[0];sign=1 if dx>=0 else -1
                mirror=(sign>0) if self.kind in ('shoulder_push','tail_pull') else (sign<0)
                if not self.reduced:tilt=(.10 if self.kind=='shoulder_push' else -.05)*sign;body_offset=(0,math.sin(age*22)*2)
            if self.tool=='computer_scroll':
                sign=-1 if self.scroll_direction in ('up','left') else 1;wave=0 if self.reduced else math.sin(age*math.tau/ .55)
                if self.kind=='swim_scroll':pose='swim' if wave>=0 else 'carry';tilt=.12*wave
                elif self.kind=='page_push':pose='push';tilt=.18*sign*abs(wave)
                else:pose='tail';tilt=-.10*wave
                if not self.reduced:body_offset=(sign*12*wave,0) if self.scroll_direction in ('left','right') else (0,sign*12*wave)
            if self.kind=='peek_menu' and age>.18:pose='binocular'
            if self.jump and .08<age<.38:lift=10*math.sin((age-.08)/.30*math.pi);y-=lift
            if self.until is not None and now>=self.until:phase='done'
        elif phase in ('windup','armed'):hand=u*.65
        if self.reduced:tilt=0.;body_offset=(0,0);yaw=1.;mirror=False
        return {'position':(round(x),round(y)),'point':point,'phase':phase,'ready':phase=='armed' and not self.ack,
                'lift':lift,'crouch':crouch,'air':air,'jump_style':self.jump,'impact':impact,'hand':hand,'direction':self.direction,'variant':self.variant,
                'windup_progress':u,'pose':pose,'mirror':mirror,'yaw':yaw,'tilt':tilt,'body_offset':body_offset,'beat_index':beat_index,
                'bob':0 if self.reduced or phase!='run' else abs(math.sin(elapsed*(24+self.variant*3)))*(3+self.variant)}
