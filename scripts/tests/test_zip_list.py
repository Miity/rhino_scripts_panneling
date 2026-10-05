# -*- coding: utf-8 -*-
"""ZipList: сторони, округлення і зведення; запуск поза Rhino: python3 tests/test_zip_list.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "parts"))
from ZipList import sides, tables, csv_text

# приклад з фото: одна сторона на одній панелі, друга розбита на дві
assert sides([51.0, 31.5, 19.0]) == (51.0, 50.5), sides([51.0, 31.5, 19.0])
assert sides([20.0, 20.0, 20.0, 20.0]) == (40.0, 40.0)  # 2+2, а не 1+3
assert sides([34.2]) == (34.2, 0.0)                      # одна лінія — стара позначка

pieces, summary = tables([("Z10", 34.2), ("Z10", 34.0), ("Z2", 35.0000001), ("Z2", 35.0),
                          ("Z1", 51.0), ("Z1", 31.5), ("Z1", 19.0), ("Z3", 12.0)])
assert [p[0] for p in pieces] == ["Z1", "Z2", "Z3", "Z10"], pieces  # Z10 після Z3, не після Z1
assert pieces[0] == ("Z1", 3, 510, 505, 51), pieces[0]             # замовляється довша сторона
assert pieces[1][4] == 35, pieces[1]                               # похибка не дає 36
assert pieces[3] == ("Z10", 2, 342, 340, 35), pieces[3]            # 34.2 → вгору до 35
assert summary == [(12, 1), (35, 2), (51, 1)], summary
text = csv_text(pieces, summary)
assert u"Z1;3;510;505;51\r\n" in text and u"Разом;4" in text, text
print("OK")
