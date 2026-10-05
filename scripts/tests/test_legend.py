# -*- coding: utf-8 -*-
"""Перевірка Legend.legend_lines (без Rhino): python3 scripts/tests/test_legend.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "markup"))
import Legend as M

got = M.legend_lines([u"P1", u"F3  L=420 × 30", u"Z2", u"A", u"sx 4", u"", None, u"TP1  H=80\nx"])
codes = [l.split()[0] for l in got]
assert codes == ["P<n>", "F<n>", "Z<n>", "TP<n>", "A–A,"], codes
assert M.legend_lines([u"Can1", u"CZ 20", u"SA 10", u"RC2  R=40"])[0].startswith("CZ")
assert M.legend_lines([u"Panel", u"PP1", u"Zip"]) == []
print("ok")
