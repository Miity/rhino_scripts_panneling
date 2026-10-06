# -*- coding: utf-8 -*-
"""Таблиця фаш (rinforzo / fascia) для розкрою.
Бере підписи, позначені parts/MarkReinf.py (UserText Reinf = H, ReinfLen = довжина ребра, см):
вибрані, або Enter — усі в документі. Довжина фаші = ребро + PLUS_CM з кожного боку, вгору до 1 см.
Результат: CSV поруч із .3dm (<файл>_reinf.csv, «;» — для Excel), таблиця в буфер обміну і в командний рядок."""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ZipList import order_cm

try:
    import Rhino
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
except ImportError:  # для tests/test_reinf_list.py поза Rhino
    Rhino = rs = sc = None

PLUS_CM = 5  # запас з кожного боку — на всяк випадок


def rows(marks):
    """marks = [(підпис, H, ребро см)] → [(підпис, H, ребро мм, фаша см)], за підписом."""
    return sorted((t, h, int(round(cm * 10)), order_cm(cm + 2 * PLUS_CM)) for t, h, cm in marks)


def totals(table):
    """[(H, штук, разом см)] за зростанням H."""
    acc = {}
    for _, h, _, cm in table:
        n, s = acc.get(h, (0, 0))
        acc[h] = (n + 1, s + cm)
    return [(h,) + acc[h] for h in sorted(acc)]


def csv_text(table):
    out = [u"Фаші — разом", u"H;Штук;Разом, см"]
    out += [u"%g;%d;%d" % t for t in totals(table)]
    out += [u"", u"Фаші — поштучно (ребро + %d см з кожного боку)" % PLUS_CM,
            u"Підпис;H;Ребро, мм;Фаша, см"]
    out += [u"%s;%g;%d;%d" % r for r in table]
    return u"\r\n".join(out) + u"\r\n"


def main():
    ids = rs.GetObjects(u"Виберіть підписи з фашею (Enter — усі в документі)", rs.filter.annotation, preselect=True)
    if not ids:
        ids = [o.Id for o in sc.doc.Objects.GetObjectList(Rhino.DocObjects.ObjectType.Annotation)]
    ids = [i for i in ids if rs.GetUserText(i, "Reinf") and rs.GetUserText(i, "ReinfLen")]
    if not ids:
        print(u"Немає підписів, позначених MarkReinf (UserText Reinf)")
        return
    table = rows([(rs.TextObjectText(i), float(rs.GetUserText(i, "Reinf")), float(rs.GetUserText(i, "ReinfLen")))
                  for i in ids])
    path = sc.doc.Path
    if path:
        path = os.path.splitext(path)[0] + "_reinf.csv"
    else:
        path = rs.SaveFileName(u"Зберегти таблицю фаш", "CSV (*.csv)|*.csv||", None, "reinf.csv")
        if not path:
            return
    with io.open(path, "w", encoding="utf-8-sig", newline="") as f:  # BOM — щоб Excel не ламав кирилицю
        f.write(csv_text(table))
    clip = u"Фаша H\tШтук\tРазом, см\n" + u"".join(u"R%g\t%d\t%d\n" % t for t in totals(table))
    clip += u"\nПідпис\tФаша, см\n" + u"".join(u"%s\t%d\n" % (r[0], r[3]) for r in table)
    rs.ClipboardText(clip)
    print(clip)
    print(u"CSV: %s (таблиця — у буфері обміну)" % path)


if __name__ == "__main__":
    main()
