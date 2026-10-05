# -*- coding: utf-8 -*-
"""З'єднати дві деталі в куті панелі (CopriZip / Seam / будь-які з різною шириною W) в одну.
Дві деталі на сусідніх ребрах сходяться в куті панелі тільки однією точкою, і між ними лишається
виріз. Вибираєш деталі (можна разом із підписами й групами, рамкою), клікаєш у виріз біля кута
(кілька кутів підряд, Enter — кінець); клік саме у виріз — він вказує, які сегменти торці. Торці обох деталей у цьому куті прибираються, зовнішні
краї подовжуються по дотичній до перетину (як _Connect), і виходить одна замкнена крива.
Останній кут рамки навколо панелі (обидва торці — одна деталь) → дві криві: зовнішня і внутрішня.
Нова крива бере шар і групу першої деталі, група другої (підпис, точки шва) переходить у неї ж.
"""
import math

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import Curve, Line, LineCurve, PolylineCurve, Vector3d
from Rhino.Geometry.Intersect import Intersection


def at(segs, p, tol):
    """[(сегмент, напрямок від p)] для сегментів, що мають кінець у p."""
    res = []
    for s in segs:
        if s.PointAtStart.DistanceTo(p) <= tol:
            res.append((s, s.TangentAtStart))
        elif s.PointAtEnd.DistanceTo(p) <= tol:
            res.append((s, -s.TangentAtEnd))
    return res


def other_end(s, p):
    return s.PointAtEnd if s.PointAtStart.DistanceTo(p) < s.PointAtEnd.DistanceTo(p) else s.PointAtStart


def in_sector(v, u, w):
    """v між напрямками u і w (кут між ними < 180°)."""
    n = Vector3d.CrossProduct(u, w)
    return n.Length > 1e-9 and Vector3d.CrossProduct(u, v) * n > 0 and Vector3d.CrossProduct(v, w) * n > 0


def shared_corner(sa, sb, click, tol):
    """Спільна вершина сегментів sa і sb, найближча до click, або None.
    sb is sa — кут, де деталь торкається сама себе (останній кут рамки навколо панелі)."""
    common = [s.PointAtStart for s in sa
              if (len(at(sa, s.PointAtStart, tol)) >= 4 if sb is sa else at(sb, s.PointAtStart, tol))]
    return min(common, key=click.DistanceTo) if common else None


def fill(sa, sb, ea, eb, c, tol):
    """(площа вирізу, ea, eb, xa, xb, o), якщо ea, eb — торці, чиї зовнішні краї сходяться в o."""
    xa, xb = other_end(ea, c), other_end(eb, c)
    ends = []
    for segs, e, x in ((sa, ea, xa), (sb, eb, xb)):
        nxt = [t for t in at(segs, x, tol) if t[0] is not e]
        if len(nxt) != 1:
            return None
        ends.append(-nxt[0][1])  # дотична зовнішнього краю, подовження за x
    ok, ta, tb = Intersection.LineLine(Line(xa, xa + ends[0]), Line(xb, xb + ends[1]), tol, False)
    if not ok or ta < -tol or tb < -tol:
        return None
    o = xa + ends[0] * ta
    area = (Vector3d.CrossProduct(xa - c, o - c).Length + Vector3d.CrossProduct(o - c, xb - c).Length) / 2
    return area, ea, eb, xa, xb, o


def join(a, b, click, tol):
    """[замкнені криві] — a і b, з'єднані в куті біля click; або рядок-помилка.
    b None — обидва торці в куті належать a: замикається рамка → дві криві, зовнішня і внутрішня."""
    sa = list(a.DuplicateSegments())  # list: сталі обгортки для `is`
    sb = sa if b is None else list(b.DuplicateSegments())
    c = shared_corner(sa, sb, click, tol)
    if c is None:
        return u"деталі не мають спільного кута"
    # Торці — два сегменти в куті, між якими лежить клік (у вирізі). Без панелі деталі симетричні:
    # пара «ребро + ребро» теж замикається (заповнює панель), тож відрізнити можна лише кліком.
    v = click - c
    best = None
    for ea, da in at(sa, c, tol):
        for eb, db in at(sb, c, tol):
            if ea is eb or Vector3d.VectorAngle(da, db) > math.radians(175):  # торець однієї по ребру другої
                continue
            if in_sector(v, da, db):
                best = fill(sa, sb, ea, eb, c, tol)
    if best is None:
        return u"клікни у виріз між деталями біля кута (або зовнішні краї не сходяться — увігнутий кут)"
    _, ea, eb, xa, xb, o = best
    rest = [s for s in sa if s is not ea and s is not eb]
    if sb is not sa:
        rest += [s for s in sb if s is not eb]
    rest += [LineCurve(p, o) for p in (xa, xb) if p.DistanceTo(o) > tol]
    joined = Curve.JoinCurves(rest, tol)
    if len(joined) != (2 if sb is sa else 1) or not all(c.IsClosed for c in joined):
        return u"деталь не замкнулась"
    out = []
    for crv in joined:
        ok, pl = crv.TryGetPolyline()  # як у CopriZip: чиста полілінія для PreparePanelCut
        if ok:
            pl.DeleteShortSegments(tol)
            if hasattr(pl, "MergeColinearSegments"):
                pl.MergeColinearSegments(1e-6, True)
            crv = PolylineCurve(pl)
        out.append(crv)
    return out


def main():
    doc = sc.doc
    tol = doc.ModelAbsoluteTolerance
    ids = rs.GetObjects(u"Виберіть деталі для з'єднання в кутах", rs.filter.curve, preselect=True) or []
    ids = [i for i in ids if rs.IsCurveClosed(i)]
    if not ids:
        print(u"Не вибрано жодної замкненої деталі.")
        return
    rs.UnselectAllObjects()
    made = []
    while True:
        p = rs.GetPoint(u"Клікни у виріз між деталями біля кута (Enter — кінець)")
        if p is None:
            break
        # пара деталей (або деталь сама з собою, j == i) зі спільною вершиною, найближчою до кліку
        best = None
        segs = [list(rs.coercecurve(k).DuplicateSegments()) for k in ids]
        for i in range(len(ids)):
            for j in range(i, len(ids)):
                c = shared_corner(segs[i], segs[j], p, tol)
                if c is not None and (best is None or c.DistanceTo(p) < best[0]):
                    best = (c.DistanceTo(p), i, j)
        if best is None:
            print(u"Біля кліку немає кута, де сходяться торці деталей.")
            continue
        _, i, j = best
        res = join(rs.coercecurve(ids[i]), None if i == j else rs.coercecurve(ids[j]), p, tol)
        if isinstance(res, str):
            print(u"Пропущено: %s" % res)
            continue
        ia, ib = ids[i], ids[j]
        attrs = doc.Objects.FindId(ia).Attributes.Duplicate()  # шар і групи першої деталі
        new = [doc.Objects.AddCurve(crv, attrs) for crv in res]
        ga, gb = rs.ObjectGroups(ia), rs.ObjectGroups(ib) if ib != ia else None
        rs.DeleteObjects(list(set([ia, ib])))
        if len(new) > 1 and not ga:  # рамка: зовнішня й внутрішня криві разом
            rs.AddObjectsToGroup(new, rs.AddGroup())
        if gb:
            members = rs.ObjectsByGroup(gb[0]) or []
            if ga:
                for m in members:
                    rs.RemoveObjectFromGroup(m, gb[0])
                rs.AddObjectsToGroup(members, ga[0])
            else:
                rs.AddObjectsToGroup(new, gb[0])
        ids = [k for k in ids if k not in (ia, ib)] + new
        made = [k for k in made if k not in (ia, ib)] + new
        doc.Views.Redraw()
    if made:
        rs.SelectObjects(made)
    print(u"З'єднано: %d деталей (виділені)" % len(made))


if __name__ == "__main__":
    main()
