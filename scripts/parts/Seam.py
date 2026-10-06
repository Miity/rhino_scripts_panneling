# -*- coding: utf-8 -*-
"""Припуск на шов (seam allowance / margine di cucitura) — окрема деталь зовні панелі.
Як CopriZip: вибираєш панель (замкнена крива) і клікаєш біля ребра (кілька підряд, Enter — кінець).
Ребро — від кута до кута (кут — злам більший за Angle); деталь — ребро + офсет на W назовні,
кінці по продовженню сусідніх ребер (геометрія — CopriZip.flap). Деталь + підпис "SA <W>" у групі,
шар Parts::Seam. Панель не змінюється.
Опція Points=Yes: ще й точки шва (логіка markup/sewing_points.py: центр ± k·Step) на копії ребра
в Parts::Seam — копія + точки в тій самій групі, що деталь.
"""
import os
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import Plane, Vector3d

try:  # стилі тексту PAT для лекал 1:1 (scripts/markup/PatternTextStyles.py)
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "markup"))
    import PatternTextStyles
except Exception:
    PatternTextStyles = None
from sewing_points import sewing_lengths  # той самий markup/ у sys.path

STICKY = "Seam"
LAYER = "Parts::Seam"


def label_frame(crv, offset, normal):
    """Точка посередині смуги і напрямок уздовж ребра (текст читається зліва направо)."""
    ok, t = crv.LengthParameter(crv.GetLength() / 2.0)
    t = t if ok else crv.Domain.Mid
    m = crv.PointAt(t)
    q = offset.PointAt(offset.ClosestPoint(m)[1])
    u = crv.TangentAt(t)
    if u.X < -1e-9 or (abs(u.X) < 1e-9 and u.Y < 0):
        u = -u
    return Plane((m + q) / 2.0, u, Vector3d.CrossProduct(normal, u))


def text_style(doc, w):
    """Стиль PAT, що влазить у смугу ширини w (≈ 0.6·w)."""
    if PatternTextStyles is None:
        return doc.DimStyles.Current
    styles = PatternTextStyles.ensure_styles(doc)
    fit = [h for h in PatternTextStyles.SERIES if h <= w * 0.6]
    return styles[fit[-1] if fit else PatternTextStyles.SERIES[0]]


def ask(gp):
    """Клік біля ребра з опціями W / Angle / Points / Step / Layout. Точка або None (Enter / Esc)."""
    w = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY, 10.0), 0.001, 1e6)
    a = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY + "_angle", 30.0), 1.0, 179.0)
    pts = Rhino.Input.Custom.OptionToggle(sc.sticky.get(STICKY + "_points", False), "No", "Yes")
    step = Rhino.Input.Custom.OptionDouble(sc.sticky.get("sew_step", 20.0), 0.001, 1e6)  # спільний із sewing_points
    gp.AddOptionDouble("W", w)
    gp.AddOptionDouble("Angle", a)
    gp.AddOptionToggle("Points", pts)
    gp.AddOptionDouble("Step", step)
    lay = Rhino.Input.Custom.OptionToggle(sc.sticky.get(STICKY + "_layout", False), "No", "Yes")
    gp.AddOptionToggle("Layout", lay)
    while True:
        r = gp.Get()
        sc.sticky[STICKY + "_layout"] = lay.CurrentValue
        sc.sticky[STICKY] = w.CurrentValue
        sc.sticky[STICKY + "_angle"] = a.CurrentValue
        sc.sticky[STICKY + "_points"] = pts.CurrentValue
        sc.sticky["sew_step"] = step.CurrentValue
        if r == Rhino.Input.GetResult.Option:
            continue
        return gp.Point() if r == Rhino.Input.GetResult.Point else None


def sewing_geometry(crv, step):
    """Копія ребра (лінія шва) + точки шва на ній (як sewing_points) — геометрія."""
    out = [crv.DuplicateCurve()]
    for s in sewing_lengths(crv.GetLength(), step):
        ok, t = crv.LengthParameter(s)
        if ok:
            out.append(Rhino.Geometry.Point(crv.PointAt(t)))
    return out


def add_sewing_points(doc, crv, step, attrs):
    """Копія ребра (лінія шва) + точки шва на ній, обидва з attrs (шар Parts::Seam)."""
    return [doc.Objects.Add(g, attrs) for g in sewing_geometry(crv, step)]


def main():
    from CopriZip import flap  # тут, а не вгорі: CopriZip сам імпортує label_frame / text_style з Seam
    sys.modules.pop("ReinfCircle", None)  # Rhino кешує модулі за сесію
    from ReinfCircle import add_part, off_panel  # Layout: розмітка на місці + деталь угорі
    doc = sc.doc
    oid = rs.GetObject(u"Виберіть панель (замкнена крива)", rs.filter.curve, preselect=True)
    if not oid:
        return
    panel = rs.coercecurve(oid)
    tol = doc.ModelAbsoluteTolerance
    ok, plane = panel.TryGetPlane(tol)
    normal = plane.ZAxis if ok else rs.ViewCPlane().ZAxis
    if not rs.IsLayer("Parts"):
        rs.AddLayer("Parts")
    if not rs.IsLayer(LAYER):
        rs.AddLayer("Seam", parent="Parts")
    attrs = doc.CreateDefaultAttributes()
    attrs.LayerIndex = doc.Layers.FindByFullPath(LAYER, -1)
    made = n_pts = 0
    while True:
        gp = Rhino.Input.Custom.GetPoint()
        gp.SetCommandPrompt(u"Клікни біля ребра під припуск на шов (Enter — кінець)")
        gp.AcceptNothing(True)
        click = ask(gp)
        if click is None:
            break
        w, angle = sc.sticky[STICKY], sc.sticky[STICKY + "_angle"]
        res = flap(panel, click, w, angle, normal, tol)
        if not isinstance(res, tuple):
            print(u"Пропущено: %s" % res)
            continue
        crv, edge, off, square = res
        te = Rhino.Geometry.TextEntity.Create(u"SA %g" % w, label_frame(edge, off, normal),
                                              text_style(doc, w), False, 0, 0)
        te.TextHorizontalAlignment = Rhino.DocObjects.TextHorizontalAlignment.Center
        te.TextVerticalAlignment = Rhino.DocObjects.TextVerticalAlignment.Middle
        full = [crv]
        if sc.sticky[STICKY + "_points"]:
            pts = sewing_geometry(edge, sc.sticky["sew_step"])
            full += pts
            n_pts += len(pts) - 1
        add_part(doc, full, te, off_panel(crv, [panel], tol), attrs, sc.sticky[STICKY + "_layout"])
        made += 1
        if square:
            print(u"Увага: %d кін. сусід гостріше 30° — кінець перпендикулярний" % square)
        doc.Views.Redraw()
    print(u"Припуск на шов: %d деталей → %s" % (made, LAYER))
    if n_pts:
        print(u"Точок шва: %d на копіях ребер у %s" % (n_pts, LAYER))


if __name__ == "__main__":
    main()
