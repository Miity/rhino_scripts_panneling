# -*- coding: utf-8 -*-
"""Таблиця довжин блискавок для замовлення.
Бере криві, позначені parts/ZipStops.py (UserText Zip = Z<n>): вибрані, або Enter — усі в документі.
Лінії з одним номером — одна блискавка: вони діляться на дві сторони з найближчими сумами довжин
(сторона може бути розбита на кілька панелей), замовляється довша сторона — без запасу,
вгору до цілого сантиметра. Сторони різняться більше ніж на DIFF_MM — попередження.
Однакові довжини зводяться в рядок «довжина × кількість».
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
DIFF_MM = 5  # сторони однієї блискавки мають бути однакові — більша різниця = помилка викрійки?


def order_cm(length_cm):
    """Округлення вгору до 1 см; хвіст похибки (35.0000001) не додає зайвий сантиметр."""
    return int(math.ceil(round(length_cm, 4)))


def sides(lengths):
    """Лінії однієї блискавки → (сторона 1, сторона 2): поділ на дві групи з найближчими сумами.
    Одна лінія — сторона 2 = 0 (стара позначка або одностороння)."""
    # ponytail: перебір 2^(n-1) поділів — миттєво для кількох ліній на блискавку, не для сотень
    if len(lengths) < 2:
        return sum(lengths), 0.0
    total, last = sum(lengths), len(lengths) - 1
    # остання лінія завжди в стороні 2: без дзеркальних дублів; сторона 1 — непорожня підмножина решти
    best = min((sum(l for k, l in enumerate(lengths[:last]) if m >> k & 1) for m in range(1, 1 << last)),
               key=lambda a: abs(total - 2 * a))
    return max(best, total - best), min(best, total - best)


def tables(zips):
    """zips = [(назва, довжина лінії в см)], лінії з однією назвою — одна блискавка →
    (поштучно [(назва, ліній, сторона 1 мм, сторона 2 мм, см до замовлення)], зведено [(см, кількість)])."""
    num = lambda s: [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", s)]
    lines = {}
    for name, cm in zips:
        lines.setdefault(name, []).append(cm)
    pieces = []
    for name in sorted(lines, key=num):
        a, b = sides(lines[name])
        pieces.append((name, len(lines[name]), int(round(a * 10)), int(round(b * 10)), order_cm(a)))
    counts = {}
    for p in pieces:
        counts[p[4]] = counts.get(p[4], 0) + 1
    return pieces, sorted(counts.items())


def csv_text(pieces, summary):
    rows = [u"Замовлення", u"Довжина, см;Кількість"]
    rows += [u"%d;%d" % s for s in summary]
    rows += [u"Разом;%d" % len(pieces), u"", u"Поштучно", u"Номер;Ліній;Сторона 1, мм;Сторона 2, мм;Замовити, см"]
    rows += [u"%s;%d;%d;%d;%d" % p for p in pieces]
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

    for p in pieces:
        if p[3] and p[2] - p[3] > DIFF_MM:
            print(u"Увага, %s: сторони різняться на %d мм (%d / %d)" % (p[0], p[2] - p[3], p[2], p[3]))
    clip = u"Довжина, см\tКількість\n" + u"".join(u"%d\t%d\n" % s for s in summary)
    rs.ClipboardText(clip)
    print(clip + u"Разом: %d шт" % len(pieces))
    print(u"CSV: %s (зведена таблиця — у буфері обміну)" % path)


if __name__ == "__main__":
    main()
