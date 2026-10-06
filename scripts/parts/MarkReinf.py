# -*- coding: utf-8 -*-
"""Позначка фаші (rinforzo / fascia) на наявному підписі — без деталі.
Вибираєш панель, далі клікаєш підписи (CZ / SA / RB…) по черзі (Enter — кінець): до тексту дописується
" R<H>" (стара R-позначка замінюється, H=0 — прибирає). Ребро панелі (кут–кут, CopriZip.pick_edge)
береться найближче до підпису — його довжина пишеться в UserText ReinfLen (см), H — у Reinf.
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
    h = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY, 60.0), 0.0, 1e6)
    a = Rhino.Input.Custom.OptionDouble(sc.sticky.get(STICKY + "_angle", 30.0), 1.0, 179.0)
    go.AddOptionDouble("H", h)
    go.AddOptionDouble("Angle", a)
    while True:
        r = go.Get()
        sc.sticky[STICKY], sc.sticky[STICKY + "_angle"] = h.CurrentValue, a.CurrentValue
        if r == Rhino.Input.GetResult.Option:
            continue
        return go.Object(0).ObjectId if r == Rhino.Input.GetResult.Object else None


HELP = u"""Опції:
  H — висота фаші (R<H> у підписі); 0 — прибрати позначку
  Angle — злам, більший за цей кут, = кут панелі (ребро під фашею — від кута до кута)"""


def main():
    print(HELP)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from CopriZip import pick_edge
    oid = rs.GetObject(u"Виберіть панель (замкнена крива)", rs.filter.curve, preselect=True)
    if not oid:
        return
    panel = rs.coercecurve(oid)
    tol = sc.doc.ModelAbsoluteTolerance
    to_cm = Rhino.RhinoMath.UnitScale(sc.doc.ModelUnitSystem, Rhino.UnitSystem.Centimeters)
    made = 0
    while True:
        go = Rhino.Input.Custom.GetObject()
        go.SetCommandPrompt(u"Клікни підпис ребра під фашею (Enter — кінець)")
        go.GeometryFilter = Rhino.DocObjects.ObjectType.Annotation
        go.AcceptNothing(True)
        tid = ask(go)
        if tid is None:
            break
        h = sc.sticky[STICKY]
        res = pick_edge(panel, rs.TextObjectPoint(tid), sc.sticky[STICKY + "_angle"], tol)
        if not isinstance(res, tuple):
            print(u"Пропущено: %s" % res)
            continue
        rs.TextObjectText(tid, relabel(rs.TextObjectText(tid), h))
        rs.SetUserText(tid, "Reinf", ("%g" % h) if h else None)
        rs.SetUserText(tid, "ReinfLen", ("%.2f" % (res[3].GetLength() * to_cm)) if h else None)
        made += 1
        if h:
            print(u"R%g: ребро %.1f см" % (h, res[3].GetLength() * to_cm))
        sc.doc.Views.Redraw()
    print(u"Позначено підписів: %d" % made)


if __name__ == "__main__":
    main()
