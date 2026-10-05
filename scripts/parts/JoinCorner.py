# -*- coding: utf-8 -*-
"""З'єднати дві деталі в куті панелі (CopriZip / Seam / будь-які з різною шириною W) в одну.
Дві деталі на сусідніх ребрах сходяться в куті панелі тільки однією точкою, і між ними лишається
виріз. Вибираєш деталі (можна разом із підписами й групами, рамкою), клікаєш у виріз біля кута
(кілька кутів підряд, Enter — кінець). Торці обох деталей у цьому куті прибираються, зовнішні
краї подовжуються по дотичній до перетину (як _Connect), і виходить одна замкнена крива.
Нова крива бере шар і групу першої деталі, група другої (підпис, точки шва) переходить у неї ж.
"""
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


def shared_corner(sa, sb, click, tol):
    """Спільна вершина сегментів sa і sb, найближча до click, або None."""
    common = [s.PointAtStart for s in sa if at(sb, s.PointAtStart, tol)]
    return min(common, key=click.DistanceTo) if common else None


def fill(sa, sb, ea, eb, c, tol):
    """(площа заповнення, ea, eb, xa, xb, o), якщо ea, eb — торці, чиї зовнішні краї сходяться в o."""
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
    """Замкнена крива — a і b, з'єднані в куті біля click; або рядок-помилка."""
    sa, sb = list(a.DuplicateSegments()), list(b.DuplicateSegments())  # list: сталі обгортки для `is`
    c = shared_corner(sa, sb, click, tol)
    if c is None:
        return u"деталі не мають спільного кута"
    # Торці — та пара сегментів у куті, що дає найменший шматок заповнення (виріз ~ W).
    # Пара «ребро + ребро» теж замикається, але заповнює всю панель — вона значно більша.
    # ponytail: якщо ребро коротше за ширину деталі, евристика може вибрати не ту пару.
    best = None
    for ea, da in at(sa, c, tol):
        for eb, db in at(sb, c, tol):
            if Vector3d.CrossProduct(da, db).Length < 1e-6:  # торець однієї по ребру другої
                continue
            r = fill(sa, sb, ea, eb, c, tol)
            if r and (best is None or r[0] < best[0]):
                best = r
    if best is None:
        return u"зовнішні краї не сходяться (паралельні або увігнутий кут)"
    _, ea, eb, xa, xb, o = best
    rest = [s for s in sa if s is not ea] + [s for s in sb if s is not eb]
    rest += [LineCurve(p, o) for p in (xa, xb) if p.DistanceTo(o) > tol]
    joined = Curve.JoinCurves(rest, tol)
    if len(joined) != 1 or not joined[0].IsClosed:
        return u"деталь не замкнулась"
    out = joined[0]
    ok, pl = out.TryGetPolyline()  # як у CopriZip: чиста полілінія для PreparePanelCut
    if ok:
        pl.DeleteShortSegments(tol)
        if hasattr(pl, "MergeColinearSegments"):
            pl.MergeColinearSegments(1e-6, True)
        out = PolylineCurve(pl)
    return out


def main():
    doc = sc.doc
    tol = doc.ModelAbsoluteTolerance
    ids = rs.GetObjects(u"Виберіть деталі для з'єднання в кутах", rs.filter.curve, preselect=True) or []
    ids = [i for i in ids if rs.IsCurveClosed(i)]
    if len(ids) < 2:
        print(u"Потрібно щонайменше дві замкнені деталі.")
        return
    rs.UnselectAllObjects()
    made = []
    while True:
        p = rs.GetPoint(u"Клікни у виріз біля кута (Enter — кінець)")
        if p is None:
            break
        # пара деталей зі спільною вершиною, найближчою до кліку
        best = None
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = rs.coercecurve(ids[i]), rs.coercecurve(ids[j])
                c = shared_corner(a.DuplicateSegments(), b.DuplicateSegments(), p, tol)
                if c is not None and (best is None or c.DistanceTo(p) < best[0]):
                    best = (c.DistanceTo(p), i, j)
        if best is None:
            print(u"Серед вибраних немає двох деталей зі спільним кутом.")
            continue
        _, i, j = best
        res = join(rs.coercecurve(ids[i]), rs.coercecurve(ids[j]), p, tol)
        if not isinstance(res, Curve):
            print(u"Пропущено: %s" % res)
            continue
        ia, ib = ids[i], ids[j]
        attrs = doc.Objects.FindId(ia).Attributes.Duplicate()  # шар і групи першої деталі
        new = doc.Objects.AddCurve(res, attrs)
        ga, gb = rs.ObjectGroups(ia), rs.ObjectGroups(ib)
        rs.DeleteObjects([ia, ib])
        if gb:
            members = rs.ObjectsByGroup(gb[0]) or []
            if ga:
                for m in members:
                    rs.RemoveObjectFromGroup(m, gb[0])
                rs.AddObjectsToGroup(members, ga[0])
            else:
                rs.AddObjectToGroup(new, gb[0])
        ids = [k for k in ids if k not in (ia, ib)] + [new]
        made = [k for k in made if k not in (ia, ib)] + [new]
        doc.Views.Redraw()
    if made:
        rs.SelectObjects(made)
    print(u"З'єднано: %d деталей (виділені)" % len(made))


if __name__ == "__main__":
    main()
