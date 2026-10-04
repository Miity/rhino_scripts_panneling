# -*- coding: utf-8 -*-
import math
import os
import sys
import unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cut"))
from RecommendCutTabs import classify, local_neck, polygon_area

SQUARE = [(0,0),(20,0),(20,20),(0,20)]
STRIP = [(0,0),(30,0),(30,2),(0,2)]
NECK = [(0,0),(10,0),(10,4),(20,4),(20,0),(30,0),(30,10),(20,10),(20,6),(10,6),(10,10),(0,10)]
SLIT = [(0,0),(30,0),(30,30),(16,30),(16,10),(14,10),(14,30),(0,30)]

class TabRecommendations(unittest.TestCase):
    def test_small_area(self):
        self.assertEqual(classify(20,20,50,1)[0], 'recommended')

    def test_long_strip_large_area(self):
        self.assertEqual(classify(200,204,50,3)[0], 'recommended')

    def test_large_square_not_flagged(self):
        self.assertIsNone(classify(400,80,50,3)[0])
        self.assertIsNone(local_neck(SQUARE,3,.001))

    def test_local_neck_is_review_not_primary(self):
        hit = local_neck(NECK,3,.001)
        self.assertAlmostEqual(hit[0], 2)
        self.assertEqual(classify(220,96,50,3,hit)[0], 'review')

    def test_slit_is_empty_space_not_paper_neck(self):
        self.assertIsNone(local_neck(SLIT,3,.001))

    def test_strip_between_opposing_sides(self):
        self.assertAlmostEqual(local_neck(STRIP,3,.001)[0],2)

    def test_orientation_and_rotation(self):
        for points in (STRIP,NECK):
            rotated=[(x*math.cos(.7)-y*math.sin(.7),x*math.sin(.7)+y*math.cos(.7)) for x,y in points]
            self.assertAlmostEqual(local_neck(rotated,3,.001)[0],2)
            self.assertAlmostEqual(local_neck(list(reversed(points)),3,.001)[0],2)

    def test_dense_segmentation(self):
        dense=[]
        for a,b in zip(STRIP,STRIP[1:]+STRIP[:1]):
            for i in range(20):
                dense.append((a[0]+(b[0]-a[0])*i/20.,a[1]+(b[1]-a[1])*i/20.))
        self.assertAlmostEqual(local_neck(dense,3,.001)[0],2)

    def test_area_far_from_origin(self):
        self.assertAlmostEqual(polygon_area([(x+1e8,y-1e8) for x,y in SQUARE]),400)

    def test_closed_duplicate_vertex(self):
        self.assertAlmostEqual(local_neck(STRIP+STRIP[:1],3,.001)[0],2)

    def test_units_scale(self):
        scaled=[(x/25.4,y/25.4) for x,y in STRIP]
        self.assertAlmostEqual(local_neck(scaled,3/25.4,.001/25.4)[0],2/25.4)

if __name__ == '__main__':
    unittest.main()
