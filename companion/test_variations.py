import unittest,json
from pathlib import Path
from model import VariationSelector,AnimationModel
from motion import GestureMotion

class VariationTests(unittest.TestCase):
    def setUp(self):self.behavior=json.loads((Path(__file__).parent/'behavior.json').read_text())
    def test_each_operation_has_three_named_choices(self):
        for op,entry in self.behavior['tools'].items():
            self.assertEqual(len(set(entry['variants'])),3,op)
            self.assertEqual(len(entry['clips']),3)
    def test_rotate_without_immediate_repeat(self):
        s=VariationSelector();choices=[s.choose('click',str(i)) for i in range(20)]
        self.assertEqual(set(choices),{0,1,2});self.assertTrue(all(a!=b for a,b in zip(choices,choices[1:])))
    def test_retry_retains_same_choice_and_does_not_consume_next(self):
        s=VariationSelector();a=s.choose('click','action1')
        self.assertEqual(s.choose('click','action1'),a);self.assertEqual(s.choose('click','action2'),1)
    def test_operations_rotate_independently(self):
        s=VariationSelector();s.choose('click','a');s.choose('click','b')
        self.assertEqual(s.choose('scroll','a'),0);self.assertEqual(s.choose('click','c'),2)
    def test_state_and_gesture_share_choice_through_approval(self):
        m=AnimationModel(self.behavior)
        for seq,state in enumerate(['executing','approval','executing']):m.event({'type':'state','seq':seq,'state':state,'tool':'computer_click','actionId':'a'})
        self.assertEqual(m.variants.choose('computer_click','a'),0)
        self.assertEqual(m.variants.choose('computer_click','b'),1)
    def test_visual_styles_preserve_actual_double_hit_count(self):
        for i,style in enumerate(self.behavior['gestures']['computer_double_click']):
            m=GestureMotion({'motionId':'m','tool':'computer_double_click','variant':i,'style':style},(0,0),(100,100),(200,200),0)
            m.dispatch(2);self.assertGreater(m.frame(2)['impact'],0);self.assertGreater(m.frame(2.16)['impact'],0);self.assertEqual(m.frame(2.33)['impact'],0)
    def test_history_is_bounded(self):
        s=VariationSelector()
        for i in range(1000):s.choose('click',str(i))
        self.assertLessEqual(len(s.remember),64)
if __name__=='__main__':unittest.main()
