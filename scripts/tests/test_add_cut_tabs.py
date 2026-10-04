# -*- coding: utf-8 -*-
"""Geometry regression checks; run outside Rhino with unittest."""
import os
import random
import sys
import unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cut"))
from AddCutTabs import tab_intervals, arc_distance


def size(interval, length):
    a, b = interval
    return b - a if b > a else length - a + b


def contains(interval, x):
    a, b = interval
    return a < x < b if b > a else x > a or x < b


class CutTabsIntervals(unittest.TestCase):
    def test_one_tab_crosses_seam(self):
        cut, gap = tab_intervals(40, [0], 2, .001)
        self.assertEqual(gap, [(39, 1)])
        self.assertEqual(cut, [(1, 39)])

    def test_keep_across_seam_is_one_piece(self):
        cut, gap = tab_intervals(40, [10], 2, .001)
        self.assertEqual(cut, [(11, 9)])
        self.assertEqual(gap, [(9, 11)])

    def test_gap_end_at_seam(self):
        cut, gap = tab_intervals(40, [39], 2, .001)
        self.assertEqual(gap, [(38, 0)])
        self.assertEqual(cut, [(0, 38)])

    def test_overlaps_including_seam_are_rejected(self):
        for centers in ([10, 10], [10, 11], [0, 39.5], [2, 4]):
            with self.assertRaises(ValueError):
                tab_intervals(40, centers, 2, .001)

    def test_no_tiny_residual_cut(self):
        with self.assertRaises(ValueError):
            tab_intervals(40, [2, 4.0001], 2, .001)

    def test_oversize_and_bad_width_rejected(self):
        for width in (0, -.1, .002, 40, 50, float('nan')):
            with self.assertRaises(ValueError):
                tab_intervals(40, [5], width, .001)

    def test_empty_input(self):
        self.assertEqual(tab_intervals(40, [], 2, .001), ([(0, 40)], []))

    def test_distance_across_seam(self):
        self.assertAlmostEqual(arc_distance(.1, 39.9, 40), .2)

    def test_random_partition_and_physical_tab_width(self):
        rng = random.Random(84)
        for unused in range(400):
            length = rng.uniform(10, 1000)
            count = rng.randint(1, 15)
            spacing = length / count
            width = spacing * rng.uniform(.01, .75)
            shift = rng.uniform(0, length)
            centers = [(shift + i * spacing) % length for i in range(count)]
            cut, gap = tab_intervals(length, centers, width, 1e-7)
            self.assertEqual(len(cut), count)
            self.assertEqual(len(gap), count)
            for interval in gap:
                self.assertAlmostEqual(size(interval, length), width, places=8)
            self.assertAlmostEqual(sum(size(v, length) for v in cut + gap), length, places=8)
            for j in range(101):
                x = length * ((j + .381) / 101)
                self.assertEqual(sum(contains(v, x) for v in cut + gap), 1)


class Bag(object):
    def __init__(self, **items):
        self.__dict__.update(items)


class FakeAttributes(object):
    def Duplicate(self):
        return FakeAttributes()

    def SetUserString(self, key, value):
        pass


class FakePart(object):
    def Dispose(self):
        pass


class FakeObjects(object):
    def __init__(self, fail_add=None, fail_hide=None):
        self.fail_add, self.fail_hide = fail_add, fail_hide
        self.add_count = 0
        self.added, self.hidden = set(), set()

    def FindId(self, source):
        return Bag(Attributes=FakeAttributes())

    def AddCurve(self, part, attributes):
        self.add_count += 1
        if self.add_count == self.fail_add:
            return 'EMPTY'
        object_id = 'new%d' % self.add_count
        self.added.add(object_id)
        return object_id

    def Hide(self, source, unused):
        if source == self.fail_hide:
            return False
        self.hidden.add(source)
        return True

    def Show(self, source, unused):
        self.hidden.remove(source)
        return True

    def Delete(self, source, unused):
        self.added.remove(source)
        return True


class CutTabsCommit(unittest.TestCase):
    def setUp(self):
        import AddCutTabs
        self.module = AddCutTabs
        self.originals = dict((key, getattr(AddCutTabs, key))
                              for key in ('sc', 'rs', 'System', 'trim_arc'))
        self.selected = []
        self.records = [{'id': 'a', 'curve': None, 'length': 40},
                        {'id': 'b', 'curve': None, 'length': 40},
                        {'id': 'untouched', 'curve': None, 'length': 40}]
        AddCutTabs.trim_arc = lambda *args: FakePart()
        AddCutTabs.System = Bag(Guid=Bag(Empty='EMPTY'))
        AddCutTabs.rs = Bag(UnselectAllObjects=lambda: None,
                            SelectObjects=lambda ids: self.selected.extend(ids))

    def tearDown(self):
        for key, value in self.originals.items():
            setattr(self.module, key, value)

    def run_commit(self, objects):
        self.module.sc = Bag(doc=Bag(Objects=objects,
            BeginUndoRecord=lambda name: 1, EndUndoRecord=lambda record: None,
            Views=Bag(Redraw=lambda: None)))
        return self.module.commit_tabs(self.records, [[5], [10], []], 2, .001)

    def test_add_failure_leaves_sources_visible_and_no_output(self):
        objects = FakeObjects(fail_add=2)
        with self.assertRaises(RuntimeError):
            self.run_commit(objects)
        self.assertFalse(objects.hidden)
        self.assertFalse(objects.added)

    def test_hide_failure_restores_sources_and_removes_output(self):
        objects = FakeObjects(fail_hide='b')
        with self.assertRaises(RuntimeError):
            self.run_commit(objects)
        self.assertFalse(objects.hidden)
        self.assertFalse(objects.added)

    def test_success_selects_cuts_and_untouched_input(self):
        objects = FakeObjects()
        self.assertEqual(self.run_commit(objects), (2, 2))
        self.assertEqual(objects.hidden, set(['a', 'b']))
        self.assertEqual(set(self.selected), set(['new1', 'new2', 'untouched']))


if __name__ == '__main__':
    unittest.main()
