# -*- coding: utf-8 -*-
"""Перевірка PrintLayout без Rhino (масштаб, порядок сторінок, товщини): python3 scripts/tests/test_print_layout.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "markup"))
import PrintLayout as M

assert M.fit(2000, 800) == (297.0, 210.0, 10)    # широка панель → горизонтальний A4, 1:10
assert M.fit(800, 2000) == (210.0, 297.0, 10)    # висока → вертикальний
assert M.fit(6300, 7200)[2] == 50                # уся схема
assert M.fit(100, 50)[2] == 1
names = [u"P10", u"TP1", u"P2", u"Pannello 3", u"P1"]
assert sorted(names, key=M.page_order) == [u"P1", u"P2", u"P10", u"TP1", u"Pannello 3"]
assert [M.weight(l) for l in ("CUT", "Parts::Zip", "2D proc::ZIP", "Parts::Canalina", "INK")] == [0.35, 0.25, 0.25, 0.25, 0.13]
print("ok")
