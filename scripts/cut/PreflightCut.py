# -*- coding: utf-8 -*-
"""Pre-flight checks before the file goes to the cutter. Read-only: nothing is changed or deleted,
the offending objects are selected and a PASS / FAIL report is printed.

Checks (add new ones to CHECKS: a function (sc.doc) -> (message, [object ids]); empty list = PASS):
  Duplicates - curves lying on each other on the same tool: the knife (cut + int) or the pen (ink).
               The machine goes over each of them, so everything gets cut / drawn twice.
"""
import os
import sys

import rhinoscriptsyntax as rs
import Rhino
import scriptcontext as sc

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sel_curve_overlap as overlap

# layers by tool (names ignore case)
TOOLS = (("knife", ("cut", "int")), ("pen", ("ink",)))
CURVE = 4


def curves_on(layers):
    """Ids of the visible, unlocked curves on the given top-level layers."""
    ids = []
    for oid in rs.ObjectsByType(CURVE, select=False) or []:
        if rs.ObjectLayer(oid).lower() in layers and rs.IsObjectNormal(oid):
            ids.append(oid)
    return ids


def duplicates(doc):
    """Per tool: the shorter / later curve of every overlapping pair (exact copies included)."""
    mm = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, doc.ModelUnitSystem)
    bad, parts = [], []
    for tool, layers in TOOLS:
        ids = curves_on(layers)
        hits = overlap.shorter_overlaps([rs.coercecurve(i) for i in ids], doc.ModelAbsoluteTolerance,
                                        overlap.OVERLAP_TOL_MM * mm, overlap.MIN_OVERLAP_MM * mm)
        if hits:
            parts.append("{} {}".format(tool, len(hits)))
            bad += [ids[k] for k in hits]
    return "Duplicate / overlapping curves ({})".format(", ".join(parts) or "none"), bad


CHECKS = [duplicates]

HELP = u"Runs every pre-flight check and selects what fails; changes nothing. Fix the selection (CurveOverlap deletes duplicates), run again until all PASS."


def main():
    print(HELP)
    failed, selected = 0, []
    for check in CHECKS:
        msg, bad = check(sc.doc)
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
