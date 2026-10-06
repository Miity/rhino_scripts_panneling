# -*- coding: utf-8 -*-
"""Reinforcement strip table for cutting.
Takes labels marked by parts/MarkReinf.py (UserText Reinf = H, ReinfLen = edge length, cm):
selected, or Enter — all in the document. Strip length = edge + PLUS_CM on each side, rounded up to 1 cm.
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

PLUS_CM = 5  # allowance on each side — just in case


def rows(marks):
    """marks = [(label, H, edge cm)] → [(label, H, edge mm, strip cm)], by label."""
    return sorted((t, h, int(round(cm * 10)), order_cm(cm + 2 * PLUS_CM)) for t, h, cm in marks)


def totals(table):
    """[(H, pieces, total cm)] by increasing H."""
    acc = {}
    for _, h, _, cm in table:
        n, s = acc.get(h, (0, 0))
        acc[h] = (n + 1, s + cm)
    return [(h,) + acc[h] for h in sorted(acc)]


def csv_text(table):
    out = [u"Strips — total", u"H;Pieces;Total, cm"]
    out += [u"%g;%d;%d" % t for t in totals(table)]
    out += [u"", u"Strips — per piece (edge + %d cm on each side)" % PLUS_CM,
            u"Label;H;Edge, mm;Strip, cm"]
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
    table = rows([(rs.TextObjectText(i), float(rs.GetUserText(i, "Reinf")), float(rs.GetUserText(i, "ReinfLen")))
                  for i in ids])
    path = sc.doc.Path
    if path:
        path = os.path.splitext(path)[0] + "_reinf.csv"
    else:
        path = rs.SaveFileName(u"Save strip table", "CSV (*.csv)|*.csv||", None, "reinf.csv")
        if not path:
            return
    with io.open(path, "w", encoding="utf-8-sig", newline="") as f:  # BOM — so Excel reads non-ASCII correctly
        f.write(csv_text(table))
    clip = u"Strip H\tPieces\tTotal, cm\n" + u"".join(u"R%g\t%d\t%d\n" % t for t in totals(table))
    clip += u"\nLabel\tStrip, cm\n" + u"".join(u"%s\t%d\n" % (r[0], r[3]) for r in table)
    rs.ClipboardText(clip)
    print(clip)
    print(u"CSV: %s (table — in the clipboard)" % path)


if __name__ == "__main__":
    main()
