# -*- coding: utf-8 -*-
"""Позначка фаші (rinforzo / fascia) на наявному підписі — без деталі.
Вибираєш підписи (CZ / SA / RB…, можна рамкою, на різних панелях): до тексту дописується
" R<H>" (стара R-позначка замінюється, H=0 — прибирає). Панель для кожного підпису — найближча (до NEAR_MM) замкнена
крива поза Parts:: (або в Parts::Panels), на якій є ребро (кут–кут, CopriZip.pick_edge): кола-позначки
без кутів пропускаються; смуги Seam / CZ — ні (не те ребро). Немає панелі поруч — підпис пропускається; ребро — найближче до підпису — його довжина пишеться в UserText ReinfLen (см), H — у Reinf.
Таблицю для замовлення робить parts/RList.py. Шар, група, положення підпису не змінюються.
"""
import os
import re
import sys

try:
    import Rhino
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
except ImportError:  # для tests/test_reinf_list.py поза Rhino
    Rhino = rs = sc = None

STICKY = "MarkReinf"
NEAR_MM = 200  # панель у цьому радіусі від підпису — перевага над деталлю (підпис стоїть на W/2 від ребра)
MARK = re.compile(r"\s+R[\d.]+$")


def relabel(text, h):
    """'CZ 30 R45', 60 → 'CZ 30 R60'; h=0 — позначку прибрати."""
    text = MARK.sub(u"", text.rstrip())
    return text + (u" R%g" % h if h else u"")


def ask(go):
    """Вибір підписів з опціями H / Angle → список id або None."""
    h = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY, 60.0), 0.0, 1e6)
    a = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY + "_angle", 30.0), 1.0, 179.0)
    go.AddOptionDouble("H", h)
    go.AddOptionDouble("Angle", a)
    while True:
        r = go.GetMultiple(1, 0)
        sc.sticky[STICKY], sc.sticky[STICKY + "_angle"] = h.CurrentValue, a.CurrentValue
        if r == Rhino.Input.GetResult.Option:
            go.EnablePreSelect(False, True)
            continue
        return [o.ObjectId for o in go.Objects()] if r == Rhino.Input.GetResult.Object else None


def closed_curves(doc):
    """[(крива, групи, деталь?)] — усі замкнені криві документа; деталь = шар Parts::*, крім Parts::Panels."""
    out = []
    for o in doc.Objects.GetObjectList(Rhino.DocObjects.ObjectType.Curve):
        if o.Geometry.IsClosed:
            path = doc.Layers[o.Attributes.LayerIndex].FullPath
            part = path.startswith("Parts::") and not path.startswith("Parts::Panels")
            out.append((o.Geometry, set(o.Attributes.GetGroupList() or []), part))
    return out


HELP = u"""Опції:
  H — висота фаші (R<H> у підписі); 0 — прибрати позначку
  Angle — злам, більший за цей кут, = кут панелі (ребро під фашею — від кута до кута)"""


def main():
    print(HELP)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from CopriZip import pick_edge
    tol = sc.doc.ModelAbsoluteTolerance
    to_cm = Rhino.RhinoMath.UnitScale(sc.doc.ModelUnitSystem, Rhino.UnitSystem.Centimeters)
    go = Rhino.Input.Custom.GetObject()
    go.SetCommandPrompt(u"Виберіть підписи ребер під фашею")
    go.GeometryFilter = Rhino.DocObjects.ObjectType.Annotation
    ids = ask(go)
    if not ids:
        return
    h, angle = sc.sticky[STICKY], sc.sticky[STICKY + "_angle"]
    cands = closed_curves(sc.doc)
    lim = NEAR_MM * Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, sc.doc.ModelUnitSystem)
    made = 0
    for tid in ids:
        p = rs.TextObjectPoint(tid)
        d = lambda c: c.PointAt(c.ClosestPoint(p)[1]).DistanceTo(p)
        groups = set(rs.coercerhinoobject(tid).Attributes.GetGroupList() or [])
        # ponytail: сортування всіх замкнених кривих на кожен підпис — ок для сотень, не для десятків тисяч
        # лише панелі поруч: смуга Seam / CZ теж замкнена, але її ребро — не те; без панелі — пропуск, не хибна довжина
        near = sorted((d(c), k) for k, (c, g, part) in enumerate(cands) if not part and not g & groups and d(c) <= lim)
        res = next((r for r in (pick_edge(cands[k][0], p, angle, tol) for _, k in near) if isinstance(r, tuple)),
                   u"панелі (замкненої кривої з кутами поза Parts::, або Parts::Panels) немає ближче %g мм" % NEAR_MM)
        if not isinstance(res, tuple):
            print(u"Пропущено %s: %s" % (rs.TextObjectText(tid), res))
            continue
        cm = res[3].GetLength() * to_cm
        rs.TextObjectText(tid, relabel(rs.TextObjectText(tid), h))
        rs.SetUserText(tid, "Reinf", ("%g" % h) if h else None)
        rs.SetUserText(tid, "ReinfLen", ("%.2f" % cm) if h else None)
        made += 1
        print(u"%s: ребро %.1f см" % (rs.TextObjectText(tid), cm))
    sc.doc.Views.Redraw()
    print(u"Позначено підписів: %d" % made)


if __name__ == "__main__":
    main()
