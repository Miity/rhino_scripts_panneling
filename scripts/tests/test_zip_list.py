# -*- coding: utf-8 -*-
"""ZipList: sides, rounding and summary; run outside Rhino: python3 tests/test_zip_list.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "parts"))
from ZipList import sides, tables, csv_text, track_table, is_track

# example from the photo: one side on one panel, the other split over two
assert sides([51.0, 31.5, 19.0]) == (51.0, 50.5), sides([51.0, 31.5, 19.0])
assert sides([20.0, 20.0, 20.0, 20.0]) == (40.0, 40.0)  # 2+2, not 1+3
assert sides([34.2]) == (34.2, 0.0)                      # one line — old mark

pieces, summary = tables([("Z10", 34.2), ("Z10", 34.0), ("Z2", 35.0000001), ("Z2", 35.0),
                          ("Z1", 51.0), ("Z1", 31.5), ("Z1", 19.0), ("Z3", 12.0)])
assert [p[0] for p in pieces] == ["Z1", "Z2", "Z3", "Z10"], pieces  # Z10 after Z3, not after Z1
assert pieces[0] == ("Z1", 3, 510, 505, 51), pieces[0]             # the longer side is ordered
assert pieces[1][4] == 35, pieces[1]                               # tolerance does not give 36
assert pieces[3] == ("Z10", 2, 342, 340, 35), pieces[3]            # 34.2 → up to 35
assert summary == [(12, 1), (35, 2), (51, 1)], summary
text = csv_text(pieces, summary)
assert u"Z1;3;510;505;51\r\n" in text and u"Total;4" in text, text

# track: one side, length = sum of lines (split over two panels)
assert is_track("Can2") and not is_track("Z2")
tracks = track_table([("Can2", 40.0), ("Can1", 30.0), ("Can1", 20.04)])
assert tracks == [("Can1", 2, 500, 51), ("Can2", 1, 400, 40)], tracks
text = csv_text(pieces, summary, tracks)
assert u"Can1;2;500;51\r\n" in text and u"Total, cm;;;91" in text, text
assert u"Track" not in csv_text(pieces, summary) and u"Zips" not in csv_text([], [], tracks)
print("OK")
