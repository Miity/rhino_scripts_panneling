# -*- coding: utf-8 -*-
"""Zip length table for ordering.
Takes curves marked by parts/ZipStops.py (UserText Zip = Z<n>): selected, or Enter — all in the document.
Lines with one number are one zip: they are split into two sides with the closest length sums
(a side may be split over several panels), the longer side is ordered — no allowance,
rounded up to a whole centimetre. Sides differing by more than DIFF_MM — warning.
Equal lengths are combined into a "length × quantity" row. A zip with one line — warning (a track?).
Track (Trk<n>) — a separate section: one side, length = sum of its lines, rounded up to 1 cm.
Output: CSV next to the .3dm (<file>_zips.csv, separator ";" — for Excel), a summary table
to the clipboard (tab separated — pastes into Excel or a sheet) and to the command line."""
import io
import math
import os
import re

try:
    import Rhino
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
except ImportError:  # for tests/test_zip_list.py outside Rhino
    Rhino = rs = sc = None

KEY = "Zip"
DIFF_MM = 5  # both sides of a zip should be equal — a larger difference = pattern error?


def order_cm(length_cm):
    """Round up to 1 cm; a tolerance tail (35.0000001) does not add an extra centimetre."""
    return int(math.ceil(round(length_cm, 4)))


def sides(lengths):
    """Lines of one zip → (side 1, side 2): split into two groups with the closest sums.
    One line — side 2 = 0 (old mark or one-sided)."""
    # ponytail: tries 2^(n-1) splits — instant for a few lines per zip, not for hundreds
    if len(lengths) < 2:
        return sum(lengths), 0.0
    total, last = sum(lengths), len(lengths) - 1
    # the last line is always in side 2: no mirrored duplicates; side 1 — non-empty subset of the rest
    best = min((sum(l for k, l in enumerate(lengths[:last]) if m >> k & 1) for m in range(1, 1 << last)),
               key=lambda a: abs(total - 2 * a))
    return max(best, total - best), min(best, total - best)


def tables(zips):
    """zips = [(name, line length in cm)], lines with one name are one zip →
    (per piece [(name, lines, side 1 mm, side 2 mm, cm to order)], summary [(cm, quantity)])."""
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


def is_track(name):
    return name.startswith("Trk")


def track_table(tracks):
    """tracks = [(name, line length in cm)] → [(name, lines, mm, cm to order)]: length — sum of lines."""
    num = lambda s: [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", s)]
    lines = {}
    for name, cm in tracks:
        lines.setdefault(name, []).append(cm)
    return [(name, len(lines[name]), int(round(sum(lines[name]) * 10)), order_cm(sum(lines[name])))
            for name in sorted(lines, key=num)]


def csv_text(pieces, summary, tracks=()):
    rows = []
    if pieces:
        rows += [u"Zips — order", u"Length, cm;Quantity"]
        rows += [u"%d;%d" % s for s in summary]
        rows += [u"Total;%d" % len(pieces), u""]
    if tracks:
        rows += [u"Track", u"Number;Lines;Length, mm;Order, cm"]
        rows += [u"%s;%d;%d;%d" % c for c in tracks]
        rows += [u"Total, cm;;;%d" % sum(c[3] for c in tracks), u""]
    if pieces:
        rows += [u"Zips — per piece", u"Number;Lines;Side 1, mm;Side 2, mm;Order, cm"]
        rows += [u"%s;%d;%d;%d;%d" % p for p in pieces]
    return u"\r\n".join(rows) + u"\r\n"


def main():
    ids = rs.GetObjects(u"Select zips (Enter — all in the document)", rs.filter.curve, preselect=True)
    if not ids:
        ids = [o.Id for o in sc.doc.Objects.GetObjectList(Rhino.DocObjects.ObjectType.Curve)]
    ids = [i for i in ids if rs.GetUserText(i, KEY)]
    if not ids:
        print(u"No curves marked by ZipStops (UserText Zip)")
        return
    to_cm = Rhino.RhinoMath.UnitScale(sc.doc.ModelUnitSystem, Rhino.UnitSystem.Centimeters)
    lines = [(rs.GetUserText(i, KEY), rs.CurveLength(i) * to_cm) for i in ids]
    pieces, summary = tables([z for z in lines if not is_track(z[0])])
    tracks = track_table([z for z in lines if is_track(z[0])])

    path = sc.doc.Path
    if path:
        path = os.path.splitext(path)[0] + "_zips.csv"
    else:
        path = rs.SaveFileName(u"Save zip table", "CSV (*.csv)|*.csv||", None, "zips.csv")
        if not path:
            return
    with io.open(path, "w", encoding="utf-8-sig", newline="") as f:  # BOM — so Excel reads non-ASCII correctly
        f.write(csv_text(pieces, summary, tracks))

    for p in pieces:
        if p[3] and p[2] - p[3] > DIFF_MM:
            print(u"Warning, %s: sides differ by %d mm (%d / %d)" % (p[0], p[2] - p[3], p[2], p[3]))
        if p[1] == 1:
            print(u"Warning, %s: one line — is it a track? (ZipStops, Type=Track)" % p[0])
    clip = u""
    if pieces:
        clip += u"Zips, cm\tQuantity\n" + u"".join(u"%d\t%d\n" % s for s in summary)
        clip += u"Total\t%d\n" % len(pieces)
    if tracks:
        clip += (u"\n" if clip else u"") + u"Track\tcm\n" + u"".join(u"%s\t%d\n" % (c[0], c[3]) for c in tracks)
        clip += u"Total, cm\t%d\n" % sum(c[3] for c in tracks)
    rs.ClipboardText(clip)
    print(clip)
    print(u"CSV: %s (summary table — in the clipboard)" % path)


if __name__ == "__main__":
    main()
