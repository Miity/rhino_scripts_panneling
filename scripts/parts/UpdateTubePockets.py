# -*- coding: utf-8 -*-
"""Оновити готові кармани TubePockets з новими параметрами (H / Trim / SA / Hem / Notch / Rigid).
Вибираєш будь-яку частину кармана (або вікном кілька) — карман перебудовується від своєї лінії шва
на місці, з тим самим номером TP<n>, шаром і боком. Змінюються тільки ті параметри, які ти змінив
в опціях; решта — свої в кожного кармана. Параметри читаються з UserText (TP_H…); у старих карманах
без UserText — з геометрії (H з підпису, SA і Trim — з контуру).
Карман = розмітка на панелі + повна деталь угорі (TP_Up): можна вибрати будь-яку з них, перебудовуються обидві.
"""
import os
import re
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.modules.pop("TubePockets", None)
import TubePockets as TP

KEYS = ("H", "Trim", "SA", "Hem", "Notch", "Rigid")
TOGGLES = ("Notch", "Rigid")


def tagged(near, n, markup):
    """Об'єкти в шарі near з UserText TP_N == n: розмітка (markup) або повна деталь."""
    return [o for o in rs.ObjectsByLayer(rs.ObjectLayer(near)) or []
            if rs.GetUserText(o, "TP_N") == n and bool(rs.GetUserText(o, "TP_Markup")) == markup]


def read_pocket(ids, tol):
    """dict з параметрами і геометрією кармана з групи ids, або рядок-причина."""
    curves = [(i, rs.coercecurve(i)) for i in ids if rs.IsCurve(i)]
    texts = [i for i in ids if rs.IsText(i)]
    m = re.match(TP.PREFIX + r"(\d+)\s+H=([\d.]+)", rs.TextObjectText(texts[0]) if texts else "")
    outline_ids = [i for i, c in curves if c.IsClosed]
    outline = [c for i, c in curves if c.IsClosed]
    opened = sorted([c for i, c in curves if not c.IsClosed], key=lambda c: -c.GetLength())
    if not m or len(outline) != 1:
        return u"не схоже на карман TP (немає підпису TP<n> або контуру)"
    if not opened:
        # ponytail: карман з SA=0 не має окремої лінії шва — відновлення з контуру не зроблене.
        return u"немає лінії шва (SA=0) — перебудуй TubePockets"
    seg, outline = opened[0], outline[0]
    ok, plane = outline.TryGetPlane(tol)
    normal = plane.ZAxis if ok else rs.ViewCPlane().ZAxis
    toward = rs.coercegeometry(texts[0]).Plane.Origin  # підпис стоїть усередині кармана
    side = lambda p: Rhino.Geometry.Vector3d.Multiply(
        Rhino.Geometry.Vector3d.CrossProduct(seg.TangentAt(seg.ClosestPoint(p)[1]), p - seg.PointAt(seg.ClosestPoint(p)[1])), normal)
    s_in = side(toward)
    pts = [c.PointAtStart for c in outline.DuplicateSegments()]
    sa = max([abs(side(p)) for p in pts if side(p) * s_in < -tol] or [0.0])
    h = float(m.group(2))
    inner = [p for p in pts if side(p) * s_in > 0 and abs(abs(side(p)) - h) < 0.01 * h]
    trim = min([seg.GetLength(Rhino.Geometry.Interval(seg.Domain.Min, seg.ClosestPoint(p)[1])) for p in inner] or [0.0])
    vals = {"H": h, "Trim": trim, "SA": sa, "Notch": float(len(opened) > 1), "Rigid": 0.0, "Hem": 0.0}
    for k in KEYS:
        v = rs.GetUserText(ids[0], "TP_" + k)
        if v:
            vals[k] = float(v)
    up = rs.GetUserText(outline_ids[0], "TP_Up")
    vals["up"] = Rhino.Geometry.Vector3d(*[float(x) for x in up.split(",")]) if up else None
    vals["markup"] = tagged(outline_ids[0], rs.GetUserText(outline_ids[0], "TP_N"), True) if up else []
    vals.update(n=int(m.group(1)), seg=seg, toward=toward, normal=normal, ids=ids,
                attrs=sc.doc.Objects.FindId(rs.coerceguid(outline_ids[0])).Attributes.Duplicate())  # шар контуру, не Fold
    return vals


def main():
    doc = sc.doc
    tol = doc.ModelAbsoluteTolerance
    sel = rs.GetObjects(u"Виберіть кармани TP (будь-яку частину)", preselect=True)
    if not sel:
        return
    groups, pockets = set(), []
    for o in sel:
        g = (rs.ObjectGroups(o) or [None])[0]
        if g is None or g in groups:
            continue
        groups.add(g)
        ids = rs.ObjectsByGroup(g)
        if rs.GetUserText(ids[0], "TP_Markup"):  # вибрано розмітку на панелі → повна деталь угорі
            full = tagged(ids[0], rs.GetUserText(ids[0], "TP_N"), False)
            g = full and (rs.ObjectGroups(full[0]) or [None])[0]
            if not g:
                print(u"Пропущено: немає повної деталі для розмітки TP%s" % rs.GetUserText(ids[0], "TP_N"))
                continue
            if g in groups:
                continue
            groups.add(g)
            ids = rs.ObjectsByGroup(g)
        res = read_pocket(ids, tol)
        if isinstance(res, dict):
            pockets.append(res)
        else:
            print(u"Пропущено: " + res)
    if not pockets:
        return
    first = pockets[0]
    print(u"TP%d зараз: H=%g Trim=%g SA=%g Hem=%g Notch=%d Rigid=%d" % ((first["n"],) + tuple(first[k] for k in KEYS)))
    go = Rhino.Input.Custom.GetOption()
    go.SetCommandPrompt(u"Нові параметри (Enter — застосувати до %d карманів)" % len(pockets))
    go.AcceptNothing(True)
    opts = dict((k, Rhino.Input.Custom.OptionDouble(first[k], 0.0, 1e6)) for k in ("H", "Trim", "SA", "Hem"))
    for k in TOGGLES:
        opts[k] = Rhino.Input.Custom.OptionToggle(bool(first[k]), "No", "Yes")
    for k in KEYS:
        (go.AddOptionToggle if k in TOGGLES else go.AddOptionDouble)(k, opts[k])
    while True:
        r = go.Get()
        if r == Rhino.Input.GetResult.Option:
            continue
        if r != Rhino.Input.GetResult.Nothing:
            return
        break
    changed = dict((k, float(opts[k].CurrentValue)) for k in KEYS if float(opts[k].CurrentValue) != first[k])
    if not changed:
        print(u"Нічого не змінено")
        return
    for p in pockets:
        p.update(changed)
        h, trim, sa, notch, rigid = p["H"], p["Trim"], p["SA"], bool(p["Notch"]), bool(p["Rigid"])
        hem = p["Hem"]
        seg, toward, up = p["seg"], p["toward"], p["up"]
        if up is not None:  # будуємо на місці розмітки, повна деталь знову піде на up
            seg = seg.DuplicateCurve()
            seg.Translate(-up)
            toward = toward - up
        res = TP.pocket(seg, toward, 0, h, trim, sa, notch, p["normal"], tol, rigid, hem)
        if not isinstance(res, tuple):
            print(u"TP%d пропущено: %s" % (p["n"], res))
            continue
        p["attrs"].RemoveFromAllGroups()
        rs.DeleteObjects(list(p["ids"]) + p["markup"])
        print(u"Оновлено: " + TP.add_pocket(doc, res + (toward,), h, trim, sa, notch, p["n"], p["attrs"], p["normal"],
                                           tol, rigid, hem, up))
    print(u"Змінено: " + ", ".join(u"%s=%g" % kv for kv in sorted(changed.items())))


if __name__ == "__main__":
    main()
