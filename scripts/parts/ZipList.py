# -*- coding: utf-8 -*-
"""Таблиця довжин блискавок для замовлення.
Бере криві, позначені parts/ZipStops.py (UserText Zip = Z<n>): вибрані, або Enter — усі в документі.
Довжина рахується з кривої зараз (без запасу) і округлюється вгору до цілого сантиметра;
однакові довжини зводяться в рядок «довжина × кількість».
Результат: CSV поруч із .3dm (<файл>_zips.csv, роздільник «;» — для Excel), зведена таблиця
в буфер обміну (через табуляцію — вставляється в Excel чи лист) і в командний рядок."""
import io
import math
import os
import re

try:
    import Rhino
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
except ImportError:  # для tests/test_zip_list.py поза Rhino
    Rhino = rs = sc = None

KEY = "Zip"


def order_cm(length_cm):
    """Округлення вгору до 1 см; хвіст похибки (35.0000001) не додає зайвий сантиметр."""
    return int(math.ceil(round(length_cm, 4)))


def tables(zips):
    """zips = [(назва, довжина в см)] → (поштучно [(назва, мм, см до замовлення)], зведено [(см, кількість)])."""
    num = lambda s: [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", s)]
    pieces = [(name, int(round(cm * 10)), order_cm(cm)) for name, cm in sorted(zips, key=lambda z: num(z[0]))]
    counts = {}
    for p in pieces:
        counts[p[2]] = counts.get(p[2], 0) + 1
    return pieces, sorted(counts.items())


def csv_text(pieces, summary):
    rows = [u"Замовлення", u"Довжина, см;Кількість"]
    rows += [u"%d;%d" % s for s in summary]
    rows += [u"Разом;%d" % len(pieces), u"", u"Поштучно", u"Номер;Довжина, мм;Замовити, см"]
    rows += [u"%s;%d;%d" % p for p in pieces]
    return u"\r\n".join(rows) + u"\r\n"


def main():
    ids = rs.GetObjects(u"Виберіть блискавки (Enter — усі в документі)", rs.filter.curve, preselect=True)
    if not ids:
        ids = [o.Id for o in sc.doc.Objects.GetObjectList(Rhino.DocObjects.ObjectType.Curve)]
    ids = [i for i in ids if rs.GetUserText(i, KEY)]
    if not ids:
        print(u"Немає кривих, позначених ZipStops (UserText Zip)")
        return
    to_cm = Rhino.RhinoMath.UnitScale(sc.doc.ModelUnitSystem, Rhino.UnitSystem.Centimeters)
    pieces, summary = tables([(rs.GetUserText(i, KEY), rs.CurveLength(i) * to_cm) for i in ids])

    path = sc.doc.Path
    if path:
        path = os.path.splitext(path)[0] + "_zips.csv"
    else:
        path = rs.SaveFileName(u"Зберегти таблицю блискавок", "CSV (*.csv)|*.csv||", None, "zips.csv")
        if not path:
            return
    with io.open(path, "w", encoding="utf-8-sig", newline="") as f:  # BOM — щоб Excel не ламав кирилицю
        f.write(csv_text(pieces, summary))

    clip = u"Довжина, см\tКількість\n" + u"".join(u"%d\t%d\n" % s for s in summary)
    rs.ClipboardText(clip)
    print(clip + u"Разом: %d шт" % len(pieces))
    print(u"CSV: %s (зведена таблиця — у буфері обміну)" % path)


if __name__ == "__main__":
    main()
