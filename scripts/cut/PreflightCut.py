# -*- coding: utf-8 -*-
"""Pre-flight checks before the file goes to the cutter. Select the parts on the canvas (a window over them);
only the selection is checked. Read-only: nothing is changed or deleted, the offending objects are selected and
a PASS / FAIL report is printed.

Checks (add new ones to CHECKS: a function (sc.doc, selected ids) -> (message, [object ids]); empty list = PASS):
  Duplicates - curves lying on each other on the same tool: the knife (cut + int) or the pen (ink).
               The machine goes over each of them, so everything gets cut / drawn twice.
  Notches    - knife notches (ConvertNotches, Tool Cut: one INT line per V leg) that are not on their place: the
               real cut of a leg (the line + the blade's Overcut past both ends) has to start on a selected CUT line
               and end inside that same line; a V needs both legs. A part moved / mirrored without its notches
               leaves them in the middle of another part — the knife would cut into it.
"""
import os
import sys

import rhinoscriptsyntax as rs
import Rhino
import scriptcontext as sc
from Rhino.Geometry import Plane, PointContainment

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sel_curve_overlap as overlap

# layers by tool (names ignore case)
TOOLS = (("knife", ("cut", "int")), ("pen", ("ink",)))
CURVE = 4
ON_LINE_MM = 0.3  # a leg's real cut may start this far from the CUT line
OVER_MM = 1.0  # blade overcut of notches made before NotchOver was stored (ConvertNotches Standard)


def curves_on(ids, layers):
    """The visible, unlocked curves among ids on the given top-level layers."""
    return [i for i in ids if rs.IsCurve(i) and rs.ObjectLayer(i).lower() in layers and rs.IsObjectNormal(i)]


def duplicates(doc, ids):
    """Per tool: the shorter / later curve of every overlapping pair (exact copies included)."""
    mm = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, doc.ModelUnitSystem)
    bad, parts = [], []
    for tool, layers in TOOLS:
        crvs = curves_on(ids, layers)
        hits = overlap.shorter_overlaps([rs.coercecurve(i) for i in crvs], doc.ModelAbsoluteTolerance,
                                        overlap.OVERLAP_TOL_MM * mm, overlap.MIN_OVERLAP_MM * mm)
        if hits:
            parts.append("{} {}".format(tool, len(hits)))
            bad += [crvs[k] for k in hits]
    return "Duplicate / overlapping curves ({})".format(", ".join(parts) or "none"), bad


def number(attrs, key, default):
    try:
        return float(attrs.GetUserString(key) or default)
    except ValueError:
        return default


def notches(doc, ids):
    """Knife notch legs whose real cut does not run from a selected CUT line to inside it, and V legs alone."""
    mm = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, doc.ModelUnitSystem)
    tol = doc.ModelAbsoluteTolerance
    cuts = []
    for i in curves_on(ids, ("cut",)):
        c = rs.coercecurve(i)
        if c.IsClosed:
            ok, plane = c.TryGetPlane(tol)
            cuts.append((c, plane if ok else Plane.WorldXY))
    legs = [doc.Objects.FindId(i) for i in curves_on(ids, ("int",))]
    legs = [o for o in legs if o.Attributes.GetUserString("NotchTool") == "Cut"]
    bad, apexes = [], []
    for o in legs:
        g = o.Geometry
        u = g.PointAtEnd - g.PointAtStart  # from the edge towards the apex
        u.Unitize()
        c = number(o.Attributes, "NotchOver", OVER_MM * mm)
        start, apex = g.PointAtStart - u * c, g.PointAtEnd + u * c  # what the blade really cuts
        apexes.append(apex)
        near = [(start.DistanceTo(crv.PointAt(crv.ClosestPoint(start)[1])), crv, pl) for crv, pl in cuts]
        d, crv, pl = min(near, key=lambda n: n[0]) if near else (None, None, None)
        if crv is None or d > ON_LINE_MM * mm + tol or crv.Contains(apex, pl, tol) != PointContainment.Inside:
            bad.append(o.Id)
    # ponytail: O(n^2) apex pairing, fine for a few hundred legs
    for k, o in enumerate(legs):
        if o.Id in bad or number(o.Attributes, "NotchW", 0.0) <= tol:  # width 0 — a slit, one line
            continue
        if not any(j != k and apexes[j].DistanceTo(apexes[k]) <= ON_LINE_MM * mm + tol for j in range(len(legs))):
            bad.append(o.Id)
    return "Knife notches off their CUT line or half a V ({} of {} legs)".format(len(bad), len(legs)), bad


CHECKS = [duplicates, notches]

HELP = u"Select the parts to check (window over the canvas); runs every pre-flight check on them and selects what fails, changes nothing. Fix the selection, run again until all PASS."


def main():
    print(HELP)
    ids = rs.GetObjects(u"Select the parts to check", preselect=True)
    if not ids:
        return
    failed, selected = 0, []
    for check in CHECKS:
        msg, bad = check(sc.doc, ids)
        print("{}  {}".format("FAIL" if bad else "PASS", msg))
        if bad:
            failed += 1
            selected += bad
    rs.UnselectAllObjects()
    if selected:
        rs.SelectObjects(selected)
    print("NOT READY for the cutter: {} check(s) failed, {} objects selected.".format(failed, len(selected))
          if failed else "All checks passed.")


if __name__ == "__main__":
    main()
