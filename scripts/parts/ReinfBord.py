# -*- coding: utf-8 -*-
"""Bordino rinforzato: смуга-підсилення висотою H уздовж ребра панелі, всередині панелі.
Вибираєш панель (замкнена крива) і клікаєш біля ребра (кілька підряд, Enter — кінець).
Ребро — від кута до кута, як у CopriZip (кут — злам дотичної більший за Angle). Ребро зсувається
всередину панелі на H (типово 6 см; буває 10), лінія продовжується прямо і обрізається іншими
сторонами панелі — смуга від кута до сторони, в яку впирається.
Опція SA — припуск на шов на внутрішньому краї (типово 0): різ на H + SA, лінія шва на H, у групі.
Панель не змінюється. Деталь на місці, шар Parts::Reinforcements, підпис "RB<n>  H=…" у групі;
нумерація RB продовжується між запусками.
"""
import os
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from System.Collections.Generic import List
from Rhino.Geometry import (Curve, CurveEnd, CurveExtensionStyle, CurveOffsetCornerStyle, CurveOrientation,
                            Plane, Point3d, Vector3d)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for _m in ("ReinfCircle", "Seam", "CopriZip"):  # Rhino тримає модулі з першого запуску за сесію
    sys.modules.pop(_m, None)
from ReinfCircle import LAYER, layer, next_number  # шар і нумерація підсилень
from Seam import label_frame, text_style  # підпис посередині смуги, стиль PAT під ширину
from CopriZip import pick_edge  # ребро від кута до кута

STICKY = "ReinfBord"
PREFIX = "RB"  # Reinforcement Bordino


def region(panel, edge, d, normal, tol):
    """(смуга між ребром і його офсетом на d всередину, обрізана панеллю; офсет) або (None, None)."""
    cw = panel.ClosedCurveOrientation(normal) == CurveOrientation.Clockwise
    tm = edge.Domain.Mid
    t = edge.TangentAt(tm)
    inward = Vector3d.CrossProduct(t, normal) if cw else Vector3d.CrossProduct(normal, t)
    mid = edge.PointAt(tm)
    offs = edge.Offset(mid + inward * d, normal, d, tol, CurveOffsetCornerStyle.Sharp)
    offs = Curve.JoinCurves(offs, tol) if offs else None
    if not offs:
        return None, None
    off = max(offs, key=lambda c: c.GetLength())
    big = panel.GetBoundingBox(True).Diagonal.Length
    ext = off.Extend(CurveEnd.Both, big, CurveExtensionStyle.Line) or off  # прямо до інших сторін
    bounds = List[Curve]()
    bounds.Add(panel)
    bounds.Add(ext)
    pts = List[Point3d]()
    pts.Add(mid + inward * (d / 2.0))
    res = Curve.CreateBooleanRegions(bounds, Plane(mid, normal), pts, False, tol)
    if res is None or res.RegionCount == 0:
        return None, None
    reg = res.RegionCurves(0)
    return (reg[0] if reg and reg[0].IsClosed else None), off


def bordino(panel, click, h, sa, angle, normal, tol):
    """(різ, [лінії шва], ребро, офсет на H) або рядок-помилка."""
    res = pick_edge(panel, click, angle, tol)
    if not isinstance(res, tuple):
        return res
    segs, _, _, edge = res
    closed = Curve.JoinCurves(segs, tol)[0]  # pick_edge замикає «майже замкнену» панель
    strip, off = region(closed, edge, h, normal, tol)
    if strip is None:
        return u"смуга не вийшла (H більша за панель? панель не в площині CPlane?)"
    if sa <= 0:
        return strip, [], edge, off
    cut = region(closed, edge, h + sa, normal, tol)[0]
    if cut is None:
        return u"смуга з SA не вийшла (H + SA більша за панель?)"
    # шов — край смуги H, що не лежить на панелі
    seams = [s for s in strip.DuplicateSegments() or []
             if any(closed.PointAt(closed.ClosestPoint(s.PointAtNormalizedLength(t))[1])
                    .DistanceTo(s.PointAtNormalizedLength(t)) > tol for t in (0.25, 0.5, 0.75))]
    return cut, list(Curve.JoinCurves(seams, tol)) if seams else [], edge, off


def ask(gp):
    """Клік біля ребра з опціями H / SA / Angle. Точка або None (Enter / Esc)."""
    unit = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, sc.doc.ModelUnitSystem)
    h = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY, 60.0 * unit), 0.001, 1e6)
    sa = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY + "_sa", 0.0), 0.0, 1e6)
    a = Rhino.Input.Custom.OptionDouble(sc.sticky.get("CopriZip_angle", 30.0), 1.0, 179.0)  # спільний з CopriZip
    gp.AddOptionDouble("H", h)
    gp.AddOptionDouble("SA", sa)
    gp.AddOptionDouble("Angle", a)
    while True:
        r = gp.Get()
        sc.sticky[STICKY] = h.CurrentValue
        sc.sticky[STICKY + "_sa"] = sa.CurrentValue
        sc.sticky["CopriZip_angle"] = a.CurrentValue
        if r == Rhino.Input.GetResult.Option:
            continue
        return gp.Point() if r == Rhino.Input.GetResult.Point else None


def main():
    doc = sc.doc
    oid = rs.GetObject(u"Виберіть панель (замкнена крива)", rs.filter.curve, preselect=True)
    if not oid:
        return
    panel = rs.coercecurve(oid)
    tol = doc.ModelAbsoluteTolerance
    ok, plane = panel.TryGetPlane(tol)
    normal = plane.ZAxis if ok else rs.ViewCPlane().ZAxis
    attrs = doc.CreateDefaultAttributes()
    attrs.LayerIndex = doc.Layers.FindByFullPath(layer(), -1)
    n = next_number(LAYER, PREFIX)
    made = 0
    while True:
        gp = Rhino.Input.Custom.GetPoint()
        gp.SetCommandPrompt(u"Клікни біля ребра під bordino (Enter — кінець)")
        gp.AcceptNothing(True)
        click = ask(gp)
        if click is None:
            break
        h, sa = sc.sticky[STICKY], sc.sticky[STICKY + "_sa"]
        res = bordino(panel, click, h, sa, sc.sticky["CopriZip_angle"], normal, tol)
        if not isinstance(res, tuple):
            print(u"Пропущено: %s" % res)
            continue
        cut, seams, edge, off = res
        label = u"%s%d  H=%g" % (PREFIX, n, h)
        te = Rhino.Geometry.TextEntity.Create(label, label_frame(edge, off, normal), text_style(doc, h), False, 0, 0)
        te.TextHorizontalAlignment = Rhino.DocObjects.TextHorizontalAlignment.Center
        te.TextVerticalAlignment = Rhino.DocObjects.TextVerticalAlignment.Middle
        new = [doc.Objects.AddCurve(c, attrs) for c in [cut] + seams] + [doc.Objects.AddText(te, attrs)]
        rs.AddObjectsToGroup(new, rs.AddGroup())
        doc.Views.Redraw()
        print(label)
        n += 1
        made += 1
    print(u"Bordino: %d → %s" % (made, LAYER))


if __name__ == "__main__":
    main()
