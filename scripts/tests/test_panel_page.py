# -*- coding: utf-8 -*-
"""Перевірка PanelPage без Rhino (масштаб, орієнтація, імена): python3 scripts/tests/test_panel_page.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "markup"))
import PanelPage as M

assert M.fit(800, 2000) == (210.0, 297.0, 10)   # завжди вертикальний A4
assert M.fit(2000, 800) == (210.0, 297.0, 15)   # широка: 2000 / 10 не влазить у 190 мм → 1:15
assert M.fit(3000, 1000)[2] == 20
assert M.fit(100, 50)[2] == 1
assert M.next_name(set()) == "P1"
assert M.next_name({"P1", "P3", "Schema", "Legenda"}) == "P4"
assert M.unique("P2", {"P2"}) == "P2 (2)" and M.unique("P2", set()) == "P2"
print("ok")
