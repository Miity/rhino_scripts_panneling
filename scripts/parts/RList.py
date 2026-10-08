# -*- coding: utf-8 -*-
"""Reinforcement strip table for cutting.
Takes labels marked by parts/MarkReinf.py (UserText Reinf = w, ReinfLen = edge length, both cm):
selected, or Enter — all in the document. Strip length = edge + Plus (asked, cm, default PLUS_CM), rounded up to 1 cm.
Output: CSV next to the .3dm (<file>_reinf.csv, ";" — for Excel), table to the clipboard and to the command line."""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ZipList import order_cm

try:
    import Rhino
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
except ImportError:  # for tests/test_reinf_list.py outside Rhino
    Rhino = rs = sc = None

PLUS_CM = 10  # default Plus: the strip is longer than the edge (half past each end), trimmed after sewing


def rows(marks, plus=PLUS_CM):
    """marks = [(label, w, edge cm)] → [(label, w, edge mm, strip cm)], by label; strip = edge + plus (cm)."""
    return sorted((t, w, int(round(cm * 10)), order_cm(cm + plus)) for t, w, cm in marks)


def totals(table):
    """[(w, pieces, total cm)] by increasing w."""
    acc = {}
    for _, w, _, cm in table:
        n, s = acc.get(w, (0, 0))
        acc[w] = (n + 1, s + cm)
    return [(w,) + acc[w] for w in sorted(acc)]


def csv_text(table, plus=PLUS_CM):
    out = [u"Strips — total", u"W, cm;Pieces;Total, cm"]
    out += [u"%g;%d;%d" % t for t in totals(table)]
    out += [u"", u"Strips — per piece (edge + %g cm)" % plus,
            u"Label;W, cm;Edge, mm;Strip, cm"]
    out += [u"%s;%g;%d;%d" % r for r in table]
    return u"\r\n".join(out) + u"\r\n"


def main():
    ids = rs.GetObjects(u"Select labels with a reinforcement strip (Enter — all in the document)", rs.filter.annotation, preselect=True)
    if not ids:
        ids = [o.Id for o in sc.doc.Objects.GetObjectList(Rhino.DocObjects.ObjectType.Annotation)]
    ids = [i for i in ids if rs.GetUserText(i, "Reinf") and rs.GetUserText(i, "ReinfLen")]
    if not ids:
        print(u"No labels marked by MarkReinf (UserText Reinf)")
        return
    plus = rs.GetReal(u"Plus — strip longer than the edge, cm (half past each end)", sc.sticky.get("RList_plus", PLUS_CM), 0.0)
    if plus is None:
        return
    sc.sticky["RList_plus"] = plus
    table = rows([(rs.TextObjectText(i), float(rs.GetUserText(i, "Reinf")), float(rs.GetUserText(i, "ReinfLen")))
                  for i in ids], plus)
    path = sc.doc.Path
    if path:
        path = os.path.splitext(path)[0] + "_reinf.csv"
    else:
        path = rs.SaveFileName(u"Save strip table", "CSV (*.csv)|*.csv||", None, "reinf.csv")
        if not path:
            return
    with io.open(path, "w", encoding="utf-8-sig", newline="") as f:  # BOM — so Excel reads non-ASCII correctly
        f.write(csv_text(table, plus))
    clip = u"Strip W\tPieces\tTotal, cm\n" + u"".join(u"R%g\t%d\t%d\n" % t for t in totals(table))
    clip += u"\nLabel\tStrip, cm\n" + u"".join(u"%s\t%d\n" % (r[0], r[3]) for r in table)
    rs.ClipboardText(clip)
    print(clip)
    print(u"CSV: %s (table — in the clipboard)" % path)


if __name__ == "__main__":
    main()
