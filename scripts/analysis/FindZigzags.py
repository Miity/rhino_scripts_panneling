# -*- coding: utf-8 -*-
"""Micro zigzags: runs of segments shorter than Size (default 0.1 mm) on the selected polylines / lines —
noise from DXF, trims or joins (e.g. 0.02 mm steps going back and forth at a corner), that PreparePanelCut,
Seams etc. trip over. Each spot gets a TextDot Zig<n> (layer Analysis::Zigzags), the view zooms to it and you
decide: Fix — the run becomes one straight segment from its first to its last point (a run shorter than Size
becomes one point; the curve's own ends stay), Skip — left as it is, its dot stays. Layer, groups, UserText of
the curve are kept (geometry replaced in place); a closed curve keeps its start point when it is not in the run.
After fixing a panel, click it again in Seams (its edges may be numbered anew).
"""
import math

try:
    import Rhino
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
except ImportError:
    Rhino = rs = sc = None

KEY = "FindZigzags.size"
LAYER = "Analysis::Zigzags"


def dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def chain(pts, closed, size):
    """Open point list to work on: a closed one starts at the start of a long segment (no run across the
    seam); its shift k, or None if every segment is short."""
    if not closed:
        return list(pts), 0
    ring = pts[:-1]
    n = len(ring)
    for k in range(n):
        if dist(ring[k], ring[(k + 1) % n]) >= size:
            return ring[k:] + ring[:k] + [ring[k]], k
    return None, None


def find_runs(pts, closed, size):
    """(i, j) of each maximal run of segments shorter than size, as indices into chain(pts, closed)."""
    work, _ = chain(pts, closed, size)
    if work is None:
        return [], None
    runs, start = [], None
    for k in range(len(work) - 1):
        short = dist(work[k], work[k + 1]) < size
        if short and start is None:
            start = k
        if not short and start is not None:
            runs.append((start, k))
            start = None
    if start is not None:
        runs.append((start, len(work) - 1))
    if runs == [(0, len(work) - 1)]:
        return [], work  # the whole curve is tiny: not a zigzag
    return runs, work


def fix(work, i, j, size):
    """work with the run (i, j) straightened: one segment i -> j, or one point if i -> j is shorter than size."""
    if dist(work[i], work[j]) >= size:
        return work[:i + 1] + work[j:]
    if j == len(work) - 1 and i > 0:
        return work[:i] + work[j:]  # the curve's end stays
    return work[:i + 1] + work[j + 1:]


def unchain(work, closed, first):
    """Back to a curve's point list; a closed one starts again at its old start point if it is still there."""
    if not closed:
        return work
    ring = work[:-1]
    for k, p in enumerate(ring):
        if dist(p, first) == 0:
            ring = ring[k:] + ring[:k]
            break
    return ring + [ring[0]]


def polyline_points(oid):
    crv = rs.coercecurve(oid)
    ok, pl = crv.TryGetPolyline() if crv is not None else (False, None)
    if not ok or pl is None:
        return None, None
    return [(p.X, p.Y, p.Z) for p in pl], crv.IsClosed


def spots(ids, size):
    """[(curve id, centre point, points in the run)] of every zigzag on the curves; and the skipped ids."""
    out, skipped = [], []
    for oid in ids:
        pts, closed = polyline_points(oid)
        if pts is None:
            skipped.append(oid)
            continue
        runs, work = find_runs(pts, closed, size)
        for i, j in runs:
            run = work[i:j + 1]
            centre = tuple(sum(c) / len(run) for c in zip(*run))
            out.append((oid, centre, run))
    return out, skipped


def fix_near(oid, centre, size):
    """Straighten the run of the curve nearest centre (found again: earlier fixes moved the indices)."""
    pts, closed = polyline_points(oid)
    if pts is None:
        return False
    runs, work = find_runs(pts, closed, size)
    if not runs:
        return False
    i, j = min(runs, key=lambda r: min(dist(p, centre) for p in work[r[0]:r[1] + 1]))
    new = unchain(fix(work, i, j, size), closed, pts[0])
    if len(new) < 2:
        return False
    pl = Rhino.Geometry.PolylineCurve([Rhino.Geometry.Point3d(*p) for p in new])
    return sc.doc.Objects.Replace(oid, pl)


def zoom(run, size):
    box = Rhino.Geometry.BoundingBox([Rhino.Geometry.Point3d(*p) for p in run])
    pad = max(box.Diagonal.Length * 5, size * 50)
    box.Inflate(pad)
    sc.doc.Views.ActiveView.ActiveViewport.ZoomBoundingBox(box)
    sc.doc.Views.Redraw()


def ask(k, n, run, fix_all):
    """'fix' / 'skip' / 'all' / 'undo' / None (stop) for spot k of n."""
    if fix_all:
        return "fix"
    go = Rhino.Input.Custom.GetOption()
    span = dist(run[0], run[-1])
    go.SetCommandPrompt(u"Zig{0} ({0} of {1}): {2} points, ends {3:.3f} apart. Enter = Fix".format(
        k + 1, n, len(run), span))
    names = ["undo", "fix", "skip", "all"]
    ids = [go.AddOption("Undo"), go.AddOption("Fix"), go.AddOption("Skip"), go.AddOption("FixAll")]
    go.AcceptNothing(True)
    r = go.Get()
    if r == Rhino.Input.GetResult.Nothing:
        return "fix"
    if r != Rhino.Input.GetResult.Option:
        return None
    return names[ids.index(go.OptionIndex())]


HELP = u"""Options:
  Size — segments shorter than this (mm) make a zigzag (default 0.1)
  At each spot: U Undo — take back the last Fix / Skip; F Fix — straighten it (Enter too); S Skip — leave it,
  its dot Zig<n> stays; FixAll — fix this and every spot left. Esc — stop, what is done stays."""


def main():
    print(HELP)
    size_mm = Rhino.Input.Custom.OptionDouble(sc.sticky.get(KEY, 0.1), 1e-6, 1e6)
    go = Rhino.Input.Custom.GetObject()
    go.SetCommandPrompt(u"Select curves to check for micro zigzags")
    go.GeometryFilter = Rhino.DocObjects.ObjectType.Curve
    go.AddOptionDouble("Size", size_mm)
    go.GroupSelect = True
    go.EnablePreSelect(True, True)
    while True:
        r = go.GetMultiple(1, 0)
        if r == Rhino.Input.GetResult.Option:
            continue
        if r != Rhino.Input.GetResult.Object:
            return
        break
    ids = [go.Object(k).ObjectId for k in range(go.ObjectCount)]
    sc.sticky[KEY] = size_mm.CurrentValue
    size = size_mm.CurrentValue * Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, sc.doc.ModelUnitSystem)

    found, skipped = spots(ids, size)
    if skipped:
        print(u"Not polylines / lines, not checked: {0}.".format(len(skipped)))
    if not found:
        print(u"No micro zigzags (segments < {0} mm) on {1} curves.".format(size_mm.CurrentValue, len(ids)))
        return
    print(u"Micro zigzags found: {0} on {1} curves.".format(
        len(found), len(set(oid for oid, _, _ in found))))
    if not rs.IsLayer(LAYER):
        rs.AddLayer(LAYER)
    dots = []
    for k, (_, centre, _) in enumerate(found):
        dot = rs.AddTextDot(u"Zig{0}".format(k + 1), centre)
        rs.ObjectLayer(dot, LAYER)
        dots.append(dot)

    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from click_undo import Steps
    steps = Steps()
    vp = sc.doc.Views.ActiveView.ActiveViewport
    view = Rhino.DocObjects.ViewportInfo(vp)
    done = []  # per spot answered: "fix" / "skip"
    fix_all = False
    k = 0
    while k < len(found):
        oid, centre, run = found[k]
        zoom(run, size)
        answer = ask(k, len(found), run, fix_all)
        if answer is None:
            break
        if answer == "undo":
            if not done:
                print(u"Nothing to undo")
            elif done[-1] == "skip" or steps.undo():  # a Skip changed nothing
                done.pop()
                k -= 1
            continue
        if answer == "all":
            fix_all, answer = True, "fix"
        if answer == "fix":
            steps.start()
            steps.change(oid)
            if fix_near(oid, centre, size):
                steps.delete(dots[k])
            else:
                print(u"Zig{0}: could not fix, left as it is.".format(k + 1))
                answer = "skip"
        done.append(answer)
        k += 1
    vp.SetViewProjection(view, True)
    sc.doc.Views.Redraw()
    fixed = sum(1 for a in done if a == "fix")
    left = len(found) - fixed
    print(u"Fixed: {0}. Left (dots Zig<n> on {1}): {2}.".format(fixed, LAYER, left))


def _self_check():
    zig = [(10, 10, 0), (10.02, 10.02, 0), (10.01, 10.0, 0), (10.03, 10.01, 0), (10.02, 10.0, 0), (10, 10.2, 0)]
    square = [(0, 0, 0), (10, 0, 0)] + zig + [(0, 10, 0), (0, 0, 0)]
    runs, work = find_runs(square, True, 0.1)
    assert len(runs) == 1
    i, j = runs[0]
    new = unchain(fix(work, i, j, 0.1), True, square[0])
    assert new[0] == (0, 0, 0) and new[-1] == (0, 0, 0) and len(new) == 6  # zigzag points gone
    # A run shorter than Size: one point; an open curve keeps its end.
    tail = [(0, 0, 0), (10, 0, 0), (10.02, 0.01, 0), (10.03, 0, 0)]
    runs, work = find_runs(tail, False, 0.1)
    assert runs == [(1, 3)] and fix(work, 1, 3, 0.1) == [(0, 0, 0), (10.03, 0, 0)]
    # A clean polyline and a tiny curve: nothing.
    assert find_runs([(0, 0, 0), (5, 0, 0), (5, 5, 0)], False, 0.1)[0] == []
    assert find_runs([(0, 0, 0), (0.01, 0, 0), (0.02, 0, 0)], False, 0.1)[0] == []
    print("self-check ok")


if __name__ == "__main__":
    if Rhino is None:
        _self_check()
    else:
        main()
