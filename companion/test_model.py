import unittest,json
from pathlib import Path
from model import placement,AnimationModel,contact_placement,hand_anchor

class ModelTests(unittest.TestCase):
    def setUp(self):self.behavior=json.loads((Path(__file__).parent/'behavior.json').read_text())
    def test_character_native_hands_align_to_target(self):
        work={'x':0,'y':0,'width':1920,'height':1200};point=(800,500)
        for size in (200,300,420):
            height=round(size*180/320)+84;pos=contact_placement(point,work,size,height);ax,ay=hand_anchor(size)
            self.assertLessEqual(abs(pos[0]+ax-point[0]),.5)
            self.assertLessEqual(abs(pos[1]+ay-point[1]),.5)
    def test_edge_contact_keeps_whole_character_on_screen(self):
        work={'x':0,'y':32,'width':1920,'height':1168}
        for point in ((0,32),(1919,1199)):
            x,y=contact_placement(point,work,300,253)
            self.assertGreaterEqual(x,0);self.assertGreaterEqual(y,32)
            self.assertLessEqual(x+300,1920);self.assertLessEqual(y+253,1200)
    def test_three_variants_for_every_tool(self):
        self.assertEqual(len(self.behavior['tools']),12)
        for tool in self.behavior['tools']:
            model=AnimationModel(self.behavior);clips=[]
            for i in range(3):model.event({'type':'state','seq':i,'state':'executing','tool':tool});clips.append(model.clip)
            self.assertEqual(len(set(clips)),3)
            for clip in clips:
                assets=Path(__file__).parent/'assets'
                file=json.loads((assets/'poses.json').read_text())[clip[5:]]['file'] if clip.startswith('pose:') else clip+'.gif'
                self.assertTrue((assets/file).exists())
    def test_delayed_events_do_not_override_approval(self):
        m=AnimationModel(self.behavior);m.event({'type':'state','seq':4,'state':'approval'})
        self.assertFalse(m.event({'type':'state','seq':3,'state':'confirmed'}));self.assertEqual(m.state,'approval')
    def test_unknown_status_is_not_success(self):
        m=AnimationModel(self.behavior);m.event({'type':'state','seq':1,'state':'surprise'})
        self.assertEqual(m.state,'idle')
    def test_hidpi_target_stays_outside_click_zone(self):
        monitors=[{'x':0,'y':0,'width':1920,'height':1200}]
        pos,point,mode=placement({'coordinateSpace':'physical','bounds':{'x':1000,'y':500,'width':1200,'height':900},'point':{'x':1800,'y':900}}, {'width':3840,'height':2400},monitors,300,250)
        self.assertEqual(point,(900,450));self.assertEqual(mode,'target')
        self.assertFalse(pos[0]<=point[0]<=pos[0]+300 and pos[1]<=point[1]<=pos[1]+250)
    def test_mixed_displays_fall_back_without_guessing(self):
        monitors=[{'x':0,'y':0,'width':1920,'height':1200},{'x':1920,'y':0,'width':1920,'height':1080}]
        _,point,mode=placement({'coordinateSpace':'physical','bounds':{'x':0,'y':0,'width':100,'height':100}}, {'width':3840,'height':2400},monitors,300,250)
        self.assertEqual(mode,'corner');self.assertIsNone(point)
    def test_unknown_capture_units_use_corner(self):
        _,point,mode=placement({'coordinateSpace':'physical','bounds':{'x':0,'y':0,'width':100,'height':100}}, {'width':1920,'height':800},[{'x':0,'y':0,'width':1920,'height':1200}],300,250)
        self.assertEqual(mode,'corner');self.assertIsNone(point)

if __name__=='__main__':unittest.main()
