import unittest
from motion import GestureMotion

class MotionTests(unittest.TestCase):
    def motion(self,**kw):return GestureMotion({'motionId':'abc','tool':'computer_click',**kw},(0,0),(800,400),(900,600),10)
    def jumping(self,reduced=False,end=(800,400)):
        return GestureMotion({'motionId':'jump','tool':'computer_click','style':{'kind':'jump_slap','jumpHeight':84,'crouchSeconds':.16,'flightSeconds':.64}},(0,0),end,(900,600),10,reduced)
    def test_jump_crouches_then_clearly_leaves_ground(self):
        m=self.jumping();c=m.frame(10+m.travel+.08);apex=m.frame(10+m.travel+.16+.32)
        self.assertEqual(c['phase'],'crouch');self.assertGreater(c['crouch'],0)
        self.assertEqual(apex['phase'],'jump');self.assertGreater(apex['lift'],80)
        self.assertLess(apex['position'][1],m.end[1]-80);self.assertEqual(apex['impact'],0);self.assertFalse(apex['ready'])
    def test_jump_lands_before_the_only_click_contact(self):
        m=self.jumping();land=m.frame(10+m.travel+m.windup+.001)
        self.assertTrue(land['ready']);self.assertEqual(land['position'],m.end);self.assertEqual(land['impact'],0)
        m.dispatch(12);self.assertEqual(m.count,1);self.assertGreater(m.frame(12)['impact'],0);self.assertEqual(m.frame(12.17)['impact'],0)
    def test_jump_disabled_by_reduced_motion_and_screen_edge(self):
        for m in (self.jumping(True),self.jumping(end=(800,0))):
            self.assertFalse(m.jump);self.assertEqual(m.frame(11)['lift'],0)
    def test_jump_fits_bounded_renderer_wait(self):
        m=self.jumping();self.assertLess(m.travel+m.windup,2.1)
    def test_run_is_continuous_and_bounded(self):
        m=self.motion();start=m.frame(10);mid=m.frame(10+m.travel/2);end=m.frame(10+m.travel)
        self.assertEqual(start['position'],(0,0));self.assertEqual(mid['position'],(400,200));self.assertEqual(end['position'],(800,400))
        self.assertEqual(mid['phase'],'run');self.assertEqual(end['phase'],'windup')
    def test_contact_requires_host_dispatch(self):
        m=self.motion();f=m.frame(15);self.assertEqual(f['phase'],'armed');self.assertEqual(f['impact'],0)
        m.ack=True;self.assertFalse(m.frame(16)['ready']);m.dispatch(16)
        self.assertEqual(m.frame(16)['impact'],1)
    def test_double_click_has_exactly_two_contact_beats(self):
        m=self.motion(tool='computer_double_click');m.dispatch(12)
        self.assertGreater(m.frame(12)['impact'],.9);self.assertGreater(m.frame(12.16)['impact'],.9)
        self.assertEqual(m.frame(12.33)['impact'],0)
    def test_drag_follows_from_to_over_driver_duration(self):
        m=GestureMotion({'motionId':'drag','tool':'computer_drag','durationMs':500},(0,0),(100,100),(200,200),1,finish=((500,500),(600,600)))
        m.dispatch(2);self.assertEqual(m.frame(2)['point'],(200,200));self.assertEqual(m.frame(2.25)['point'],(400,400));self.assertEqual(m.frame(2.5)['point'],(600,600))
    def test_reduced_motion_has_no_run_or_bounce(self):
        m=GestureMotion({'motionId':'r','tool':'computer_click'},(0,0),(900,300),(1000,500),1,True)
        f=m.frame(1);self.assertEqual(f['position'],(900,300));self.assertEqual(f['bob'],0)
    def test_settle_does_not_cut_off_double_hit(self):
        m=self.motion(tool='computer_double_click');m.dispatch(12);m.settle(12.01)
        self.assertEqual(m.frame(12.16)['phase'],'contact');self.assertEqual(m.frame(13)['phase'],'done')
if __name__=='__main__':unittest.main()
