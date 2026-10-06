# -*- coding: utf-8 -*-
"""MarkReinf / RList: label and strip length; run outside Rhino: python3 tests/test_reinf_list.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "parts"))
from MarkReinf import relabel
from RList import rows, totals, csv_text

assert relabel(u"ZC 30", 60) == u"ZC 30 R60"
assert relabel(u"ZC 30 R45", 60) == u"ZC 30 R60"   # old mark is replaced
assert relabel(u"ZC20 R45", 0) == u"ZC20"           # H=0 — remove
t = rows([(u"ZC 30 R60", 60.0, 120.3), (u"ZC 20 R45", 45.0, 80.0), (u"ZC 30 R60", 60.0, 119.99999)])
assert t[0] == (u"ZC 20 R45", 45.0, 800, 90), t     # +5 cm on each side
assert t[2][3] == 131, t                            # 130.3 → 131
assert totals(t) == [(45.0, 1, 90), (60.0, 2, 261)], totals(t)
assert u"R" in csv_text(t)
print("ok")
