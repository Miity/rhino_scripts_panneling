# -*- coding: utf-8 -*-
"""Check of Legend.legend_lines (without Rhino): python3 scripts/tests/test_legend.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "markup"))
import Legend as M

got = M.legend_lines([u"P1", u"F5  l=420", u"Z2", u"A", u"sx 4", u"", None, u"T1  h=8\nx"], "EN")
codes = [l.split()[0] for l in got]
assert codes == ["P<n>", "F<w>", "Z<n>", "T<n>", "A–A,"], codes
got = [l.split()[0] for l in M.legend_lines([u"Can1", u"CZ2 R6", u"C1", u"RC2  r=4", u"RD1", u"RO1  r=15", u"R6  l=130"])]
assert got == ["CZ<w>", "C<w>", "Can<n>", "R<w>", "RC<n>", "RD<n>", "RO<n>"], got  # CZ2 R6 — both CZ and R
assert M.legend_lines([u"Panel", u"PP1", u"Zip", u"ZC 20", u"Trk1", u"TP1  H=80"]) == []  # old English codes — not ours

assert M.legend_lines([u"P1", u"A"]) == [M.ENTRIES[0][1][2], M.ENTRIES[-1][1][2]]  # default IT
assert M.legend_lines([u"C1"], "EN") == [u"C<w> — seam allowance (with notches), width w"]
print("ok")
