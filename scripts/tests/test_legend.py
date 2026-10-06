# -*- coding: utf-8 -*-
"""Check of Legend.legend_lines (without Rhino): python3 scripts/tests/test_legend.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "markup"))
import Legend as M

got = M.legend_lines([u"P1", u"S3  L=420 × 30", u"Z2", u"A", u"sx 4", u"", None, u"TP1  H=80\nx"])
codes = [l.split()[0] for l in got]
assert codes == ["P<n>", "S<n>", "Z<n>", "TP<n>", "A–A,"], codes
assert M.legend_lines([u"Trk1", u"ZC 20", u"SA 10", u"RC2  R=40"])[0].startswith("ZC")
assert M.legend_lines([u"Panel", u"PP1", u"Zip"]) == []

assert M.legend_lines([u"P1", u"A"], "IT") == [M.ENTRIES[0][1][2], M.ENTRIES[-1][1][2]]
assert M.legend_lines([u"SA 10"], "EN") == [u"SA W — seam allowance, width W"]
print("ok")
