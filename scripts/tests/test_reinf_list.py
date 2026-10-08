# -*- coding: utf-8 -*-
"""MarkReinf / RList: label and strip length; run outside Rhino: python3 tests/test_reinf_list.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "parts"))
from MarkReinf import relabel
from RList import rows, totals, csv_text

assert relabel(u"CZ3", 6) == u"CZ3 R6"
assert relabel(u"CZ3 R4.5", 6) == u"CZ3 R6"         # old mark is replaced
assert relabel(u"CZ2 R4.5", 0) == u"CZ2"            # W=0 — remove
t = rows([(u"CZ3 R6", 6.0, 120.3), (u"CZ2 R4.5", 4.5, 80.0), (u"CZ3 R6", 6.0, 119.99999)])
assert t[0] == (u"CZ2 R4.5", 4.5, 800, 90), t       # default Plus 10 cm
assert t[2][3] == 131, t                            # 130.3 → 131
assert totals(t) == [(4.5, 1, 90), (6.0, 2, 261)], totals(t)
assert rows([(u"CZ3 R6", 6.0, 120.3)], 5)[0][3] == 126  # Plus 5
assert u"edge + 5 cm" in csv_text(t, 5)
print("ok")
