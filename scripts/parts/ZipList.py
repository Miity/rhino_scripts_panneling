# -*- coding: utf-8 -*-
"""Zip length table for ordering.
Takes the number texts made by parts/ZipStops.py (UserText Zip = Z<n>, ZipLine, ZipTrim): selected,
or Enter — all in the document. Length is measured live: the marked panel edge / curve (found again from
ZipEdge) minus Trim at its ends; if the edge is not found — the length stored when marked (ZipLen), with a warning.
Lines with one number are one zip: they are split into two sides with the closest length sums
(a side may be split over several panels), the longer side is ordered — no allowance,
rounded up to a whole centimetre. Sides differing by more than DIFF_MM — warning.
Equal lengths are combined into a "length × quantity" row. A zip with one line — warning (a track?).
Track (canalina, Can<n>) — a separate section: one side, length = sum of its lines, rounded up to 1 cm.
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
LINE = "ZipLine"
TRIM = "ZipTrim"
LEN = "ZipLen"
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
    return name.startswith("Can")


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


def line_length(t, tol):
    """(length between the stops of the edge a number text marks, document units; warning or None).
    The edge is found again (ZipStops.edge_of) and measured live; not found — the length stored when marked."""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import ZipStops  # needs Rhino; the pure functions above stay testable without it
    edge = ZipStops.edge_of(t, tol)[0]
    try:
        t0, t1 = [float(x) for x in rs.GetUserText(t, TRIM).split(",")]
    except Exception:
        t0 = t1 = 0.0
    if edge is not None:
        return edge.GetLength() - t0 - t1, None
    try:
        return float(rs.GetUserText(t, LEN)) - t0 - t1, u"edge not found (panel / curve deleted or changed) — length when marked"
    except Exception:
        return None, u"edge not found (panel / curve deleted?) — not counted"


def main():
    ids = rs.GetObjects(u"Select zip numbers (Enter — all in the document)", rs.filter.annotation, preselect=True)
    if not ids:
        ids = [o.Id for o in sc.doc.Objects.GetObjectList(Rhino.DocObjects.ObjectType.Annotation)]
    ids = [i for i in ids if rs.GetUserText(i, KEY) and rs.GetUserText(i, LINE)]
    if not ids:
        print(u"No zip numbers made by ZipStops (text with UserText Zip / ZipLine)")
        return
    to_cm = Rhino.RhinoMath.UnitScale(sc.doc.ModelUnitSystem, Rhino.UnitSystem.Centimeters)
    lines = []
    for i in ids:
        length, warn = line_length(i, sc.doc.ModelAbsoluteTolerance)
        if warn:
            print(u"Warning, %s: %s" % (rs.GetUserText(i, KEY), warn))
        if length is not None:
            lines.append((rs.GetUserText(i, KEY), length * to_cm))
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
