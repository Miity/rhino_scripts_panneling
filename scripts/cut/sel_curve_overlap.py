# -*- coding: utf-8 -*-
"""Delete exact duplicate curves (Rhino's SelDup), then for every pair of overlapping curves
select the shorter one (the one lying under a longer curve); for near-identical copies,
select all but one.

Works on the preselected curves if there are any, otherwise on all curves in the document.
"""
import rhinoscriptsyntax as rs
import Rhino
import scriptcontext as sc

# ponytail: curves closer than this count as lying on each other. Copies, re-drawn
# edges and polyline approximations of the same curve drift 0.002-0.1 mm apart, far
# above the document tolerance. Distinct curves closer than this (or crossing at
# under ~0.5 degrees) will be treated as overlapping too; lower it if that happens.
OVERLAP_TOL_MM = 0.5
# ponytail: filters out noise overlaps at shared endpoints/tangencies; bump this if
# real short overlaps still get missed, or lower it if short duplicates get skipped.
MIN_OVERLAP_MM = 1.0


def shorter_overlaps(curves, tol, overlap_tol, min_len):
    """Indices of curves that overlap a longer curve (or an equal one listed earlier)."""
    Intersection = Rhino.Geometry.Intersect.Intersection
    lengths = [c.GetLength() for c in curves]
    hits = set()
    # ponytail: O(n^2) pairwise check, fine for typical pattern curve counts;
    # if this gets slow on large models, cull pairs with an RTree first.
    for i in range(len(curves)):
        for j in range(i + 1, len(curves)):
            events = Intersection.CurveCurve(curves[i], curves[j], tol, overlap_tol)
            if events and any(e.IsOverlap and curves[i].GetLength(e.OverlapA) >= min_len for e in events):
                # equal lengths (duplicates) -> the later one, so one copy stays unselected
                hits.add(i if lengths[i] < lengths[j] else j)
    return hits


def delete_exact_duplicates(ids):
    """Delete the curves among ids that Rhino's SelDup marks as copies; return the rest."""
    rs.UnselectAllObjects()
    rs.Command("_SelDup", False)
    dups = set(str(id) for id in rs.SelectedObjects() or [])
    gone = [id for id in ids if str(id) in dups]
    if gone:
        rs.DeleteObjects(gone)
    return [id for id in ids if str(id) not in dups], len(gone)


def sel_curve_overlap():
    ids = [id for id in rs.SelectedObjects() or [] if rs.ObjectType(id) == 4]  # 4 = curves
    if not ids:
        ids = rs.ObjectsByType(4, select=False) or []
    if len(ids) < 2:
        print("Потрібно щонайменше дві криві.")
        return

    ids, deleted = delete_exact_duplicates(ids)
    if deleted:
        print("Видалено {} точних дублікатів.".format(deleted))

    mm = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, sc.doc.ModelUnitSystem)
    hits = shorter_overlaps([rs.coercecurve(id) for id in ids], sc.doc.ModelAbsoluteTolerance,
                            OVERLAP_TOL_MM * mm, MIN_OVERLAP_MM * mm)

    rs.UnselectAllObjects()
    if hits:
        rs.SelectObjects([ids[k] for k in hits])
        print("Виділено {} коротших кривих під довшими.".format(len(hits)))
    else:
        print("Коротших кривих під довшими не знайдено.")


if __name__ == "__main__":
    sel_curve_overlap()
