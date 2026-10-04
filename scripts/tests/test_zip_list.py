# -*- coding: utf-8 -*-
"""ZipList: округлення і зведення; запуск поза Rhino: python3 tests/test_zip_list.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "parts"))
from ZipList import tables, csv_text

pieces, summary = tables([("Z10", 34.2), ("Z2", 35.0000001), ("Z1", 34.01), ("Z3", 12.0)])
assert [p[0] for p in pieces] == ["Z1", "Z2", "Z3", "Z10"], pieces  # Z10 після Z3, не після Z1
assert pieces[0] == ("Z1", 340, 35), pieces[0]                     # 34.01 → вгору до 35
assert pieces[1][2] == 35, pieces[1]                               # похибка не дає 36
assert summary == [(12, 1), (35, 3)], summary
assert u"35;3\r\n" in csv_text(pieces, summary) and u"Разом;4" in csv_text(pieces, summary)
print("OK")
