# -*- coding: utf-8 -*-
"""Нарізка панелей під ширину рулону матеріалу.

1. Виберіть панелі (замкнені криві, зазвичай CUT).
2. Виберіть матеріал: замкнений прямокутник (Origin) або дві його лінії — верх і низ.
3. Enter на запитах = відступ 50 і шов 10 (одиниці документа, мм).

Для кожної панелі, що вилазить за лінію матеріалу:
- основна панель обрізається рівно по лінії матеріалу і закривається нею;
- шматок, що вилазить, відрізається на `шов` всередині матеріалу, отримує ще `шов` припуску
  (разом 2 × шов перекриття) і відсувається на `відступ` — вище верхньої або нижче нижньої лінії;
- лінія шва (на `шов` від лінії матеріалу) малюється на INK і на панелі, і на відрізаному шматку;
- внутрішні об'єкти відрізаного шматка (INK/INT: лінії, точки, текст) ріжуться по шву і їдуть разом із ним;
- кожна пара шматків підписується біля шва однаковою літерою: A і A, B і B, … Z, AA, AB …
  Лічильник зберігається у файлі, тож наступний запуск продовжує з наступної літери.
Сумісність: IronPython 2.7 / CPython 3 (Rhino 8).
"""
import os
import sys

import Rhino
import System
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import (Curve, Interval, LineCurve, Plane, PointContainment,
                            Rectangle3d, Transform, Vector3d)

try:  # стилі тексту PAT для лекал 1:1 (scripts/markup/PatternTextStyles.py)
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "markup"))
    import PatternTextStyles
except Exception:
    PatternTextStyles = None

SEAM_LAYER = "INK"
LABEL_KEY = ("SplitPanelsToMaterial", "next_label")


def letters(i):
    """0 → A, 25 → Z, 26 → AA …"""
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def text_style(doc, chord_len, room):
    """Стиль PAT: літера ≈ ¼ довжини шва, але влазить у відрізаний шматок (room) і не більше 20 мм."""
    if PatternTextStyles is None:
        return doc.DimStyles.Current
    styles = PatternTextStyles.ensure_styles(doc)
    fit = [h for h in PatternTextStyles.SERIES if h <= min(chord_len / 4.0, room / 2.0, 20)]
    return styles[fit[-1] if fit else PatternTextStyles.SERIES[0]]


def make_label(text, pt, u, style):
    if u.X < -1e-9 or (abs(u.X) < 1e-9 and u.Y < 0):
        u = -u  # текст читається зліва направо, площина не дзеркальна
    te = Rhino.Geometry.TextEntity.Create(text, Plane(pt, u, Vector3d.CrossProduct(Vector3d.ZAxis, u)),
                                          style, False, 0, 0)
    te.TextHorizontalAlignment = Rhino.DocObjects.TextHorizontalAlignment.Center
    te.TextVerticalAlignment = Rhino.DocObjects.TextVerticalAlignment.Middle
    return te


def label_is_free(doc, bb, region, ignore, tol):
    """Рамка підпису всередині шматка і не зачіпає інших об'єктів (текст, точки, лінії)."""
    corners = [bb.Corner(x, y, True) for x in (True, False) for y in (True, False)]
    if any(region.Contains(c, Plane.WorldXY, tol) != PointContainment.Inside for c in corners):
        return False
    box = Rectangle3d(Plane.WorldXY, bb.Min, bb.Max).ToNurbsCurve()
    for obj in doc.Objects:
        if obj.Id in ignore or not obj.Visible:
            continue
        g = obj.Geometry
        ob = g.GetBoundingBox(True)
        if ob.Max.X < bb.Min.X or ob.Min.X > bb.Max.X or ob.Max.Y < bb.Min.Y or ob.Min.Y > bb.Max.Y:
            continue
        if not isinstance(g, Curve):
            return False
        if bb.Contains(g.PointAtStart) or Rhino.Geometry.Intersect.Intersection.CurveCurve(g, box, tol, tol):
            return False
    return True


def add_label(doc, text, chord, shift, u, style, region, ignore, attrs, tol):
    """Ставить підпис біля шва: спершу по центру, далі зсуває вздовж шва, поки не знайде вільне місце."""
    for t in (0.5, 0.4, 0.6, 0.3, 0.7, 0.2, 0.8, 0.1, 0.9):
        te = make_label(text, chord.PointAtNormalizedLength(t) + shift, u, style)
        if label_is_free(doc, te.GetBoundingBox(True), region, ignore, tol):
            break
    else:  # ponytail: вільного місця на шві немає — лишаємо по центру; далі від шва не шукаємо.
        te = make_label(text, chord.PointAtNormalizedLength(0.5) + shift, u, style)
    return doc.Objects.AddText(te, attrs)


def label_pair(doc, text, piece, comp, chords, plane, to_local, seam, move, ignore, attrs, tol):
    """Однакова літера біля шва: на основній панелі (piece) і на відрізаному шматку (comp, ще до зсуву)."""
    if not chords:
        return []
    chord = max(chords, key=lambda c: c.GetLength())
    room = seam - comp.GetBoundingBox(to_local).Min.Y  # глибина шматка від шва до краю
    style = text_style(doc, chord.GetLength(), room)
    th = style.TextHeight * style.DimensionScale
    n = plane.YAxis
    moved = comp.DuplicateCurve()
    moved.Translate(move)
    return [add_label(doc, text, chord, n * 1.5 * th, plane.XAxis, style, piece, ignore, attrs, tol),
            add_label(doc, text, chord, move - n * min(1.5 * th, room / 2.0), plane.XAxis, style,
                      moved, ignore, attrs, tol)]


def boolean_and(a, b, tol):
    try:
        res = Curve.CreateBooleanIntersection(a, b, tol)
    except TypeError:  # Rhino 6: без допуску
        res = Curve.CreateBooleanIntersection(a, b)
    return list(res or [])


def material_frames(curves):
    """Дві лінії матеріалу → [(plane, to_local)]; вісь Y площини дивиться всередину матеріалу."""
    if len(curves) == 1:  # прямокутник матеріалу: беремо дві найдовші сторони
        ok, poly = curves[0].TryGetPolyline()
        if not ok:
            return None
        segs = sorted(poly.GetSegments(), key=lambda s: -s.Length)[:2]
        lines = [(s.From, s.To) for s in segs]
    else:
        if not all(c.IsLinear() for c in curves):
            return None
        lines = [(c.PointAtStart, c.PointAtEnd) for c in curves]
    frames = []
    for i, (a, b) in enumerate(lines):
        o1, o2 = lines[1 - i]
        u = b - a
        u.Unitize()
        n = Vector3d.CrossProduct(Vector3d.ZAxis, u)
        if Vector3d.Multiply(o1 + (o2 - o1) * 0.5 - a, n) < 0:
            n = -n
        plane = Plane(a, u, n)
        frames.append((plane, Transform.PlaneToPlane(plane, Plane.WorldXY)))
    return frames


def rect(plane, u0, u1, h0, h1):
    return Rectangle3d(plane, Interval(u0, u1), Interval(h0, h1)).ToNurbsCurve()


def inside_pieces(crv, region, tol):
    """Шматки кривої всередині замкненого регіону."""
    params = []
    for e in Rhino.Geometry.Intersect.Intersection.CurveCurve(crv, region, tol, tol) or []:
        params.append(e.ParameterA)
        if e.IsOverlap:
            params.append(e.OverlapA.T1)
    pieces = (crv.Split(params) if params else None) or [crv]
    return [p for p in pieces if region.Contains(p.PointAtNormalizedLength(0.5), Plane.WorldXY, tol)
            != PointContainment.Outside]


def merge(intervals):
    out = []
    for a, b in sorted(intervals):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def cut_panel(panel, plane, to_local, seam, tol):
    """Ріже панель по одній лінії матеріалу.
    Повертає None (не вилазить) або (основні шматки, [(відрізаний шматок, [лінії шва])])."""
    bb = panel.GetBoundingBox(to_local)  # x — уздовж лінії, y — від лінії всередину матеріалу
    eps = max(10 * tol, 0.1 * seam)  # виліт до 1 мм — шум оцифровки, не ріжемо
    if bb.Min.Y > -eps:
        return None
    u0, u1, h0, h1 = bb.Min.X - 1, bb.Max.X + 1, bb.Min.Y - 1, bb.Max.Y + 1
    over = [c for c in boolean_and(panel, rect(plane, u0, u1, h0, 0), tol)
            if c.GetBoundingBox(to_local).Min.Y < -eps]
    # ponytail: шматок ріжеться смугою вздовж лінії шириною = його габарит ± 2×шов; на дуже
    # похилих боках (>45°) край припуску стає прямим, а не продовжує бік панелі.
    spans = merge([(b.Min.X - 2 * seam, b.Max.X + 2 * seam)
                   for b in (c.GetBoundingBox(to_local) for c in over)])
    offs = []
    for a, b in spans:
        for comp in boolean_and(panel, rect(plane, a, b, h0, 2 * seam), tol):
            if comp.GetBoundingBox(to_local).Min.Y > -eps:
                continue  # у смугу потрапив лише шматок у межах матеріалу
            chord = LineCurve(plane.PointAt(a - 1, seam), plane.PointAt(b + 1, seam))
            offs.append((comp, inside_pieces(chord, comp, tol)))
    if not offs:
        return None
    main = boolean_and(panel, rect(plane, u0, u1, 0, h1), tol)
    return main, offs


def carry_objects(doc, region, chords, plane, seam, move, skip, tol):
    """Ріже внутрішні об'єкти по шву і посуває те, що в `region` за швом (ближче до краю)."""
    rb = region.GetBoundingBox(True)
    xf = Transform.Translation(move)

    def goes(p):
        return (Vector3d.Multiply(p - plane.Origin, plane.YAxis) < seam
                and region.Contains(p, Plane.WorldXY, tol) != PointContainment.Outside)

    settings = Rhino.DocObjects.ObjectEnumeratorSettings()
    settings.NormalObjects = True
    settings.LockedObjects = False
    for obj in list(doc.Objects.GetObjectList(settings)):
        if obj.Id in skip:
            continue
        g = obj.Geometry
        b = g.GetBoundingBox(True)
        if b.Max.X < rb.Min.X or b.Min.X > rb.Max.X or b.Max.Y < rb.Min.Y or b.Min.Y > rb.Max.Y:
            continue
        if isinstance(g, Curve):
            params = [e.ParameterA for c in chords
                      for e in Rhino.Geometry.Intersect.Intersection.CurveCurve(g, c, tol, tol) or []]
            pieces = (g.Split(params) if params else None) or [g]
            flags = [goes(p.PointAtNormalizedLength(0.5)) for p in pieces]
            if not any(flags):
                continue
            if all(flags):
                doc.Objects.Transform(obj.Id, xf, True)
                skip.add(obj.Id)
                continue
            for p, f in zip(pieces, flags):
                if f:
                    p.Transform(xf)
                new_id = doc.Objects.AddCurve(p, obj.Attributes)
                if f:
                    skip.add(new_id)
            doc.Objects.Delete(obj.Id, True)
        elif goes(b.Center):
            doc.Objects.Transform(obj.Id, xf, True)
            skip.add(obj.Id)


def seam_attributes(doc):
    idx = doc.Layers.FindByFullPath(SEAM_LAYER, -1)
    if idx < 0:
        idx = doc.Layers.Add(SEAM_LAYER, System.Drawing.Color.Blue)
    attrs = Rhino.DocObjects.ObjectAttributes()
    attrs.LayerIndex = idx
    return attrs


def run(doc, panel_ids, frames, gap, seam):
    """Ріже панелі; повертає (кількість розрізаних панелей, кількість відсунутих шматків)."""
    tol = doc.ModelAbsoluteTolerance
    seam_attrs = seam_attributes(doc)
    skip = set(panel_ids)
    n_panels = n_offs = 0
    label_i = int(doc.Strings.GetValue(*LABEL_KEY) or 0)
    for pid in panel_ids:
        obj = doc.Objects.FindId(pid)
        pieces, moved = [obj.Geometry], []
        for plane, to_local in frames:
            move = -plane.YAxis * gap
            nxt = []
            for p in pieces:
                res = cut_panel(p, plane, to_local, seam, tol)
                if res is None:
                    nxt.append(p)
                    continue
                main, offs = res
                nxt.extend(main)
                for comp, chords in offs:
                    carry_objects(doc, comp, chords, plane, seam, move, skip, tol)
                    skip.update(label_pair(doc, letters(label_i), p, comp, chords, plane, to_local,
                                           seam, move, panel_ids, seam_attrs, tol))
                    label_i += 1
                    for c in chords:
                        skip.add(doc.Objects.AddCurve(c, seam_attrs))
                        c2 = c.DuplicateCurve()
                        c2.Translate(move)
                        skip.add(doc.Objects.AddCurve(c2, seam_attrs))
                    comp.Translate(move)
                    moved.append(comp)
            pieces = nxt
        if not moved:
            continue
        for c in pieces + moved:
            skip.add(doc.Objects.AddCurve(c, obj.Attributes))
        doc.Objects.Delete(pid, True)
        n_panels += 1
        n_offs += len(moved)
    doc.Strings.SetString(LABEL_KEY[0], LABEL_KEY[1], str(label_i))
    return n_panels, n_offs


def main():
    panel_ids = rs.GetObjects("Виберіть панелі (замкнені криві)", rs.filter.curve, preselect=True)
    if not panel_ids:
        return
    panel_ids = [i for i in panel_ids if rs.IsCurveClosed(i) and rs.IsCurvePlanar(i)]
    mat_ids = rs.GetObjects("Виберіть матеріал: прямокутник або дві лінії (верх і низ)",
                            rs.filter.curve, minimum_count=1, maximum_count=2)
    if not mat_ids:
        return
    frames = material_frames([rs.coercecurve(i) for i in mat_ids])
    if not frames:
        print("Матеріал: потрібен прямокутник-полілайн або дві прямі лінії")
        return
    gap = rs.GetReal("Відсунути відрізані шматки на", 50.0, 0.0)
    if gap is None:
        return
    seam = rs.GetReal("Шов / припуск від лінії матеріалу", 10.0, 0.0)
    if seam is None:
        return
    panel_ids = [i for i in panel_ids if i not in mat_ids]

    rs.EnableRedraw(False)
    try:
        n_panels, n_offs = run(sc.doc, panel_ids, frames, gap, seam)
    finally:
        rs.EnableRedraw(True)
    print("Розрізано панелей: {}, відсунуто шматків: {}".format(n_panels, n_offs))


if __name__ == "__main__":
    main()
