# -*- coding: utf-8 -*-
"""Позначка фаші (rinforzo / fascia) на наявному підписі — без деталі.
Вибираєш підписи (CZ / SA / RB…, можна рамкою, на різних панелях): до тексту дописується
" R<H>" (стара R-позначка замінюється, H=0 — прибирає). Панель для кожного підпису — найближча замкнена
крива поза Parts:: (крім Parts::Panels — самі деталі CZ / SA теж замкнені, їх пропускаємо); ребро
(кут–кут, CopriZip.pick_edge) — найближче до підпису — його довжина пишеться в UserText ReinfLen (см), H — у Reinf.
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


def panels(doc):
    """Замкнені криві-кандидати в панелі: не деталі з Parts:: (крім Parts::Panels)."""
    out = []
    for o in doc.Objects.GetObjectList(Rhino.DocObjects.ObjectType.Curve):
        path = doc.Layers[o.Attributes.LayerIndex].FullPath
        if o.Geometry.IsClosed and (not path.startswith("Parts::") or path.startswith("Parts::Panels")):
            out.append(o.Geometry)
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
    cands = panels(sc.doc)
    made = 0
    for tid in ids:
        p = rs.TextObjectPoint(tid)
        if p is None or not cands:
            continue
        # ponytail: перебір усіх замкнених кривих на кожен підпис — ок для сотень, не для десятків тисяч
        panel = min(cands, key=lambda c: c.PointAt(c.ClosestPoint(p)[1]).DistanceTo(p))
        res = pick_edge(panel, p, angle, tol)
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
