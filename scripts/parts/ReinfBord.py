# -*- coding: utf-8 -*-
"""Bordino rinforzato: смуга-підсилення висотою H уздовж ребра панелі, всередині панелі.
Вибираєш панель (замкнена крива) і клікаєш біля ребра (кілька підряд, Enter — кінець).
Як CopriZip (CopriZip.flap, inward), тільки всередину: ребро від кута до кута (кут — злам дотичної
більший за Angle) + офсет на H (типово 6 см; буває 10) всередину панелі, кінці — по сусідніх ребрах
(сусід гостріше 30° — кінець перпендикулярний). Дві смуги в куті з'єднує JoinCorner.
Опція SA — припуск на шов на внутрішньому краї (типово 0): різ на H + SA, лінія шва на H, у групі.
Панель не змінюється. Деталь на місці, шар Parts::Reinforcements, підпис "RB<n>  H=…" (≈ H/10, на чверті ребра, вздовж внутрішньої лінії) у групі;
нумерація RB продовжується між запусками.
"""
import os
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import Curve

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for _m in ("ReinfCircle", "Seam", "CopriZip"):  # Rhino тримає модулі з першого запуску за сесію
    sys.modules.pop(_m, None)
from ReinfCircle import LAYER, layer, next_number, text_style  # шар, нумерація, стиль PAT ≈ H/10 (як RC)
from Seam import label_frame  # напрямок підпису вздовж ребра (читається зліва направо)
from CopriZip import flap  # ребро кут–кут + офсет, кінці по сусідніх ребрах

STICKY = "ReinfBord"
PREFIX = "RB"  # Reinforcement Bordino


def bordino(panel, click, h, sa, angle, normal, tol):
    """(різ, [лінії шва], ребро, офсет на H, к-сть перпендикулярних кінців) або рядок-помилка."""
    res = flap(panel, click, h + sa, angle, normal, tol, inward=True)
    if not isinstance(res, tuple) or sa <= 0:
        return res if not isinstance(res, tuple) else (res[0], [], res[1], res[2], res[3])
    cut, edge, _, square = res
    strip = flap(panel, click, h, angle, normal, tol, inward=True)
    if not isinstance(strip, tuple):
        return strip
    crv, _, off, _ = strip
    # шов — край смуги H, що не лежить на ребрі й сусідніх сторонах (тобто не на різі)
    seams = [g for g in crv.DuplicateSegments() or []
             if any(cut.PointAt(cut.ClosestPoint(g.PointAtNormalizedLength(t))[1])
                    .DistanceTo(g.PointAtNormalizedLength(t)) > tol for t in (0.25, 0.5, 0.75))]
    return cut, list(Curve.JoinCurves(seams, tol)) if seams else [], edge, off, square


def label_place(edge, off, normal, gap):
    """(площина, вертикальне вирівнювання) підпису: на чверті ребра, вздовж внутрішньої лінії (офсет H),
    з боку смуги на відстані gap — посередині ребра вже підписи CopriZip / ZipStops."""
    half = edge.Trim(edge.Domain.T0, edge.LengthParameter(edge.GetLength() / 2.0)[1]) or edge
    plane = label_frame(half, off, normal)
    ok, t = half.LengthParameter(half.GetLength() / 2.0)
    m = half.PointAt(t if ok else half.Domain.Mid)
    q = off.PointAt(off.ClosestPoint(m)[1])
    toward = m - q  # від внутрішньої лінії до ребра, тобто в смугу
    toward.Unitize()
    plane.Origin = q + toward * gap
    up = plane.YAxis * toward > 0
    return plane, (Rhino.DocObjects.TextVerticalAlignment.Bottom if up else Rhino.DocObjects.TextVerticalAlignment.Top)


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
        cut, seams, edge, off, square = res
        label = u"%s%d  H=%g" % (PREFIX, n, h)
        style = text_style(doc, h)
        plane, valign = label_place(edge, off, normal, style.TextHeight * 0.5)
        te = Rhino.Geometry.TextEntity.Create(label, plane, style, False, 0, 0)
        te.TextHorizontalAlignment = Rhino.DocObjects.TextHorizontalAlignment.Center
        te.TextVerticalAlignment = valign
        new = [doc.Objects.AddCurve(c, attrs) for c in [cut] + seams] + [doc.Objects.AddText(te, attrs)]
        rs.AddObjectsToGroup(new, rs.AddGroup())
        doc.Views.Redraw()
        print(label)
        if square:
            print(u"Увага: %d кін. сусід гостріше 30° — кінець перпендикулярний" % square)
        n += 1
        made += 1
    print(u"Bordino: %d → %s" % (made, LAYER))


if __name__ == "__main__":
    main()
