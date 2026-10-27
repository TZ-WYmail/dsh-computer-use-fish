import unittest,json,hashlib
from pathlib import Path
from collections import Counter
from model import VariationSelector,resolve_clip
from motion import GestureMotion
BASE=Path(__file__).parent
class RichMotionTests(unittest.TestCase):
    def setUp(self):self.behavior=json.loads((BASE/'behavior.json').read_text())
    def motion(self,tool,variant=0,**extra):
        return GestureMotion({'motionId':'x','tool':tool,'variant':variant,'style':self.behavior['gestures'][tool][variant],**extra},(20,100),(200,100),(300,300),1,finish=((500,200),(600,400)))
    def test_pointer_choices_have_different_choreography_kinds(self):
        for tool,styles in self.behavior['gestures'].items():self.assertEqual(len({s['kind'] for s in styles}),3,tool)
    def test_alternating_double_uses_two_whole_character_poses(self):
        m=self.motion('computer_double_click');m.dispatch(3)
        a,b=m.frame(3),m.frame(3.16)
        self.assertEqual((a['pose'],b['pose']),('tap-left','tap-right'));self.assertNotEqual(a['mirror'],b['mirror'])
        self.assertEqual(m.count,2);self.assertEqual(m.frame(3.33)['impact'],0)
    def test_turn_and_rush_prepare_differently(self):
        turn=self.motion('computer_click',1);rush=self.motion('computer_click',2)
        a=turn.frame(1+turn.travel+turn.windup/2);b=rush.frame(1+rush.travel+rush.windup/2)
        self.assertIsNone(a['pose']);self.assertNotEqual(b['position'],rush.end);self.assertFalse(a['ready']);self.assertFalse(b['ready'])
    def test_carry_and_push_face_different_directions(self):
        a,b=self.motion('computer_drag',0),self.motion('computer_drag',1)
        a.dispatch(3);b.dispatch(3)
        self.assertNotEqual(a.frame(3.1)['mirror'],b.frame(3.1)['mirror'])
        self.assertEqual(a.frame(3.5)['point'],(600,400));self.assertEqual(b.frame(3.5)['point'],(600,400))
    def test_scroll_up_and_down_move_body_in_correct_directions(self):
        up,down=self.motion('computer_scroll',direction='up'),self.motion('computer_scroll',direction='down')
        up.dispatch(3);down.dispatch(3)
        self.assertAlmostEqual(up.frame(3.1)['body_offset'][1],-down.frame(3.1)['body_offset'][1])
        self.assertNotEqual(up.frame(3.1)['body_offset'][1],0)
    def test_swim_changes_between_recovery_and_outstretched_pose(self):
        m=self.motion('computer_scroll');m.dispatch(3)
        self.assertNotEqual(m.frame(3.1)['pose'],m.frame(3.4)['pose'])
    def test_long_wait_does_not_sleep_immediately(self):
        self.assertEqual(resolve_clip('sleep','computer_wait','executing',1),'idle')
        self.assertEqual(resolve_clip('sleep','computer_wait','executing',9),'sleep')
    def test_shuffled_bags_are_fair_without_immediate_repeat(self):
        s=VariationSelector();choices=[s.choose('click',str(i)) for i in range(90)]
        self.assertEqual(Counter(choices),{0:30,1:30,2:30});self.assertTrue(all(a!=b for a,b in zip(choices,choices[1:])))
    def test_generated_poses_are_valid_whole_character_files(self):
        poses=json.loads((BASE/'assets/poses.json').read_text());self.assertEqual(len(poses),8)
        for name,m in poses.items():
            self.assertEqual(hashlib.sha256((BASE/'assets'/m['file']).read_bytes()).hexdigest(),m['sha256'])
            l,t,r,b=m['bbox'];x,y=m['anchor'];self.assertTrue(l<=x<=r and t<=y<=b,name)
if __name__=='__main__':unittest.main()
