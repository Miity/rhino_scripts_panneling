# -*- coding: utf-8 -*-
"""З'єднати дві деталі в куті панелі (CopriZip / Seam / будь-які з різною шириною W) в одну.
Дві деталі на сусідніх ребрах сходяться в куті панелі тільки однією точкою, і між ними лишається
виріз. Вибираєш деталі (можна разом із підписами й групами, рамкою), клікаєш у виріз біля кута
(кілька кутів підряд, Enter — кінець); клік саме у виріз — він вказує, які сегменти торці. Торці обох деталей у цьому куті прибираються, зовнішні
краї подовжуються по дотичній до перетину (як _Connect), і виходить одна замкнена крива.
Останній кут рамки навколо панелі (обидва торці — одна деталь) → лишається тільки зовнішній контур.
Деталі всередину панелі (ReinfBord) у куті перекриваються, а не мають вирізу → просто об'єднання
(внутрішні краї до перетину); клік біля кута.
Нова крива бере шар і групу першої деталі, група другої (підпис, точки шва) переходить у неї ж.
Деталі з Layout=Yes (розмітка на панелі + повна деталь угорі, UserText PartLink): можна вибрати розмітку
або деталь угорі і клікати в кут будь-де з них — з'єднуються деталі вгорі, розмітка на панелі перебудовується
(лінії з'єднаної деталі, що не лежать на ребрах панелі).
"""
import math
import os
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import AreaMassProperties, Curve, Line, LineCurve, PolylineCurve, Transform, Vector3d
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
    b None — обидва торці в куті належать a: рамка замикається → лише зовнішній контур."""
    sa = list(a.DuplicateSegments())  # list: сталі обгортки для `is`
    sb = sa if b is None else list(b.DuplicateSegments())
    c = shared_corner(sa, sb, click, tol)
    if c is None:
        return u"деталі не мають спільного кута"
    joined = overlap(a, b, tol)
    if joined is None:
        joined = gap(sa, sb, c, click, tol)
        if isinstance(joined, str):
            return joined
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


def overlap(a, b, tol):
    """[об'єднання a і b], якщо вони перекриваються (смуги всередину панелі, ReinfBord); інакше None."""
    # ponytail: рамка зі смуг усередину (останній кут — деталь сама з собою) не обробляється
    if b is None:
        return None
    u = Curve.CreateBooleanUnion([a, b], tol)
    if not u or len(u) != 1:
        return None
    area = lambda c: AreaMassProperties.Compute(c).Area
    ua, aa, ab = area(u[0]), area(a), area(b)
    return [u[0]] if max(aa, ab) * 1.001 < ua < 0.999 * (aa + ab) else None  # справжнє перекриття, не дотик і не та сама


def gap(sa, sb, c, click, tol):
    """[замкнені криві] — деталі з вирізом у куті c, торці геть, зовнішні краї до перетину; або рядок-помилка."""
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
    if sb is sa:  # рамка замкнулась: внутрішній контур (= край панелі) не потрібен, лишається зовнішній
        joined = [max(joined, key=lambda c: c.GetBoundingBox(True).Diagonal.Length)]
    return joined


def link_of(i):
    """(PartLink, вектор LayoutUp) повної деталі або (None, None)."""
    up = rs.GetUserText(i, "LayoutUp")
    return (rs.GetUserText(i, "PartLink"), Vector3d(*[float(x) for x in up.split(",")])) if up else (None, None)


def linked(link, markup):
    """Об'єкти з UserText PartLink == link: розмітка (markup) або повна деталь."""
    return [o.Id for o in sc.doc.Objects.FindByUserString("PartLink", link, True)
            if bool(o.Attributes.GetUserString("PartMarkup")) == markup]


def to_full(ids):
    """Розмітку (відкрита крива з PartMarkup) замінює її повною деталлю (замкнений контур угорі)."""
    out = []
    for i in ids:
        if rs.GetUserText(i, "PartMarkup"):
            i = next((k for k in linked(rs.GetUserText(i, "PartLink"), False)
                      if rs.IsCurve(k) and rs.IsCurveClosed(k)), None)
        if i is not None and rs.IsCurveClosed(i) and i not in out:
            out.append(i)
    return out


def moved(crv, v):
    c = crv.DuplicateCurve()
    c.Transform(Transform.Translation(v))
    return c


def rebuild_markup(doc, res, parts, up, tol):
    """Розмітка з'єднаної деталі: res (угорі) зсунуті на -up, без ребер панелі. parts — [(id контуру, PartLink)]
    вихідних деталей (ще в документі). Стара розмітка-криві видаляються, підписи — в групу розмітки першої."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    sys.modules.pop("ReinfCircle", None)  # Rhino кешує модулі за сесію
    from ReinfCircle import off_panel
    edges, old = [], []
    for i, link in parts:
        marks = linked(link, True)
        curves = [rs.coercecurve(m) for m in marks if rs.IsCurve(m)]
        # ребра панелі = сегменти вихідної деталі (на місці), що не лежать на її розмітці
        edges += [g for g in moved(rs.coercecurve(i), -up).DuplicateSegments()
                  if not curves or off_panel(g, curves, tol)]
        old.append(marks)
    first = [m for m in old[0] if rs.IsCurve(m)]
    if not first:
        return
    attrs = doc.Objects.FindId(first[0]).Attributes.Duplicate()
    groups = rs.ObjectGroups(first[0])
    new = [doc.Objects.AddCurve(c, attrs) for r in res for c in off_panel(moved(r, -up), edges, tol)]
    rest = [m for marks in old[1:] for m in marks if not rs.IsCurve(m)]  # підписи розмітки другої деталі
    for m in rest:
        rs.RemoveObjectFromAllGroups(m)
        rs.SetUserText(m, "PartLink", parts[0][1])
    rs.DeleteObjects([m for marks in old for m in marks if rs.IsCurve(m)])
    if groups:
        rs.AddObjectsToGroup(new + rest, groups[0])


def main():
    doc = sc.doc
    tol = doc.ModelAbsoluteTolerance
    ids = rs.GetObjects(u"Виберіть деталі для з'єднання в кутах", rs.filter.curve, preselect=True) or []
    ids = to_full(ids)
    if not ids:
        print(u"Не вибрано жодної замкненої деталі (чи розмітки з деталлю вгорі).")
        return
    rs.UnselectAllObjects()
    made = []
    while True:
        click = rs.GetPoint(u"Клікни у виріз між деталями біля кута (Enter — кінець)")
        if click is None:
            break
        # пара деталей (або деталь сама з собою, j == i) зі спільною вершиною, найближчою до кліку;
        # клік у розмітці на панелі → той самий кут угорі (+LayoutUp)
        best = None
        segs = [list(rs.coercecurve(k).DuplicateSegments()) for k in ids]
        for i in range(len(ids)):
            up = link_of(ids[i])[1]
            for p in [click] + ([click + up] if up else []):
                for j in range(i, len(ids)):
                    c = shared_corner(segs[i], segs[j], p, tol)
                    if c is not None and (best is None or c.DistanceTo(p) < best[0]):
                        best = (c.DistanceTo(p), i, j, p)
        if best is None:
            print(u"Біля кліку немає кута, де сходяться торці деталей.")
            continue
        _, i, j, p = best
        res = join(rs.coercecurve(ids[i]), None if i == j else rs.coercecurve(ids[j]), p, tol)
        if isinstance(res, str):
            print(u"Пропущено: %s" % res)
            continue
        ia, ib = ids[i], ids[j]
        (la, up), lb = link_of(ia), link_of(ib)[0]
        if la:
            rebuild_markup(doc, res, [(ia, la)] + ([(ib, lb)] if lb and ib != ia else []), up, tol)
        attrs = doc.Objects.FindId(ia).Attributes.Duplicate()  # шар і групи першої деталі (і PartLink)
        new = [doc.Objects.AddCurve(crv, attrs) for crv in res]
        ga, gb = rs.ObjectGroups(ia), rs.ObjectGroups(ib) if ib != ia else None
        rs.DeleteObjects(list(set([ia, ib])))
        if gb:
            members = rs.ObjectsByGroup(gb[0]) or []
            if ga:
                for m in members:
                    rs.RemoveObjectFromGroup(m, gb[0])
                rs.AddObjectsToGroup(members, ga[0])
            else:
                rs.AddObjectsToGroup(new, gb[0])
            if la:
                for m in members:
                    rs.SetUserText(m, "PartLink", la)
        ids = [k for k in ids if k not in (ia, ib)] + new
        made = [k for k in made if k not in (ia, ib)] + new
        doc.Views.Redraw()
    if made:
        rs.SelectObjects(made)
    print(u"З'єднано: %d деталей (виділені)" % len(made))


if __name__ == "__main__":
    main()
