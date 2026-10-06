# -*- coding: utf-8 -*-
"""MarkReinf / RList: підпис і довжина фаші; запуск поза Rhino: python3 tests/test_reinf_list.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "parts"))
from MarkReinf import relabel
from RList import rows, totals, csv_text

assert relabel(u"CZ 30", 60) == u"CZ 30 R60"
assert relabel(u"CZ 30 R45", 60) == u"CZ 30 R60"   # стара позначка замінюється
assert relabel(u"CZ20 R45", 0) == u"CZ20"           # H=0 — прибрати
t = rows([(u"CZ 30 R60", 60.0, 120.3), (u"CZ 20 R45", 45.0, 80.0), (u"CZ 30 R60", 60.0, 119.99999)])
assert t[0] == (u"CZ 20 R45", 45.0, 800, 90), t     # +5 см з кожного боку
assert t[2][3] == 131, t                            # 130.3 → 131
assert totals(t) == [(45.0, 1, 90), (60.0, 2, 261)], totals(t)
assert u"R" in csv_text(t)
print("ok")
