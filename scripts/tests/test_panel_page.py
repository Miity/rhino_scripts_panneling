# -*- coding: utf-8 -*-
"""Перевірка PanelPage без Rhino (масштаб, орієнтація, імена): python3 scripts/tests/test_panel_page.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "markup"))
import PanelPage as M

pw, ph, n = M.fit(220, 100)                      # маленька панель 22 см: заповнює ширину рамки, а не 1:2
assert (pw, ph) == (210.0, 297.0) and abs(220 / n - 190 / 1.05) < 1e-9
assert abs(M.fit(800, 2000)[2] - 2000 / 277.0 * 1.05) < 1e-9   # висока — по висоті
assert M.next_name(set()) == "P1"
assert M.next_name({"P1", "P3", "Schema", "Legenda"}) == "P4"
assert M.unique("P2", {"P2"}) == "P2 (2)" and M.unique("P2", set()) == "P2"
print("ok")
