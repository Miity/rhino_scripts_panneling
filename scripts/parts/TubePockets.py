# -*- coding: utf-8 -*-
"""Кармани для труб у тенті (tasca per tubo).
Вибираєш панель (замкнена крива), потім клікаєш біля ребра (кілька підряд, Enter — кінець).
Ребро — від кута до кута (кут — злам дотичної більший за Angle, як у CopriZip). Карман — відрізок
ребра ширини W по центру (середина за довжиною; 0 — усе ребро), зсунутий на висоту H всередину панелі;
зсунута лінія коротша на Trim з кожного кінця (карман звужується).
Припуск на шов SA іде від ребра назовні панелі. Лінія шва — копія відрізка в групі.
Опція Notch — мітка центру (риска через лінію шва по середині). Деталь лежить на місці, у шарі
Parts::Pockets, з підписом "TP<n>  H=…" у групі; нумерація TP продовжується. Панель не змінюється.
Опція Rigid — карман жорстким офсетом (curves/OffsetRigid.py): копія відрізка без зміни форми,
зсунута на H по нормалі в центрі кармана (Rigid=No — стандартний офсет; припуск SA завжди стандартний).
Опції W / H / Trim / SA / Notch / Rigid / Angle — у запиті кліку, запам'ятовуються між запусками.
"""
import os
import re
import sys

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc
from Rhino.Geometry import Curve, CurveOffsetCornerStyle, CurveOrientation, LineCurve, Vector3d

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for _m in ("CopriZip", "Seam"):  # Rhino тримає модулі з першого запуску за сесію — беремо свіжі
    sys.modules.pop(_m, None)
from CopriZip import pick_edge  # ребро панелі від кута до кута біля кліку
from Seam import label_frame, text_style  # той самий підпис уздовж смуги і стиль PAT
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "curves"))
sys.modules.pop("OffsetRigid", None)
from OffsetRigid import shift  # жорсткий офсет: зсув по нормалі в точці

STICKY = "TubePockets"
LAYER = "Parts::Pockets"
PREFIX = "TP"  # Tube Pocket


def offset(crv, toward, d, normal, tol):
    """Офсет відкритої кривої на d у бік точки toward, у тому ж напрямку, що crv. None — не вдався."""
    offs = crv.Offset(toward, normal, d, tol, CurveOffsetCornerStyle.Sharp)
    offs = Curve.JoinCurves(offs, tol) if offs else None
    if not offs:
        return None
    o = max(offs, key=lambda c: c.GetLength())
    if o.PointAtStart.DistanceTo(crv.PointAtStart) > o.PointAtEnd.DistanceTo(crv.PointAtStart):
        o.Reverse()
    return o


def pocket_side(seg, toward, h, normal, tol, rigid):
    """Верх кармана: офсет seg на h у бік toward; rigid — копія seg, зсунута по нормалі в середині seg."""
    if not rigid:
        return offset(seg, toward, h, normal, tol)
    ok, tm = seg.LengthParameter(seg.GetLength() / 2.0)
    v = shift(seg, tm if ok else seg.Domain.Mid, normal, toward, h)
    if v is None:
        return None
    c = seg.DuplicateCurve()
    c.Translate(v)
    return c


def trim_len(crv, a, b):
    """Шматок crv між довжинами a і b від початку. None — не вийшло."""
    ok0, t0 = crv.LengthParameter(a)
    ok1, t1 = crv.LengthParameter(b)
    return crv.Trim(t0, t1) if ok0 and ok1 and t1 > t0 else None


def pocket(crv, click, w, h, trim, sa, notch, normal, tol, rigid=False):
    """(контур, лінія шва, мітка центру або None); рядок — причина, чому не вийшло."""
    length = crv.GetLength()
    seg = crv.DuplicateCurve() if w <= 0 or w >= length else trim_len(crv, (length - w) / 2.0, (length + w) / 2.0)
    if seg is None:
        return u"не вдалось вирізати відрізок ширини W"
    ok, t = seg.ClosestPoint(click)
    base = seg.PointAt(t)
    away = base - (click - base)  # дзеркало кліку через лінію: бік припуску
    inner = pocket_side(seg, click, h, normal, tol, rigid)
    if inner is None:
        return u"офсет на H не вдався (крива неплоска чи самоперетин?)"
    li = inner.GetLength()
    inner = trim_len(inner, trim, li - trim) if trim > 0 else inner
    if inner is None:
        return u"Trim %g з кожного боку довший за карман" % trim
    outer = offset(seg, away, sa, normal, tol) if sa > 0 else seg.DuplicateCurve()
    if outer is None:
        return u"офсет припуску SA не вдався"
    edges = [outer, LineCurve(outer.PointAtStart, seg.PointAtStart), LineCurve(seg.PointAtStart, inner.PointAtStart),
             inner, LineCurve(inner.PointAtEnd, seg.PointAtEnd), LineCurve(seg.PointAtEnd, outer.PointAtEnd)]
    joined = Curve.JoinCurves([e for e in edges if e.GetLength() > tol], tol)
    if len(joined) != 1 or not joined[0].IsClosed:
        return u"контур кармана не замкнувся"
    mark = None
    if notch:
        ok, tm = seg.LengthParameter(seg.GetLength() / 2.0)
        m = seg.PointAt(tm)
        q = inner.PointAt(inner.ClosestPoint(m)[1])
        d = q - m
        d.Unitize()
        # ponytail: заходить на H/10 у карман від лінії шва; якщо треба фіксовану глибину — окрема опція.
        mark = LineCurve(outer.PointAt(outer.ClosestPoint(m)[1]) if sa > 0 else m, m + d * (h / 10.0))
    return joined[0], seg, mark


def add_pocket(doc, res, h, trim, sa, notch, n, attrs, normal, tol, rigid=False):
    """Додає карман (контур, лінія шва, мітка, підпис) у групу; параметри — UserText для UpdateTubePockets."""
    outline, seg, mark, toward = res
    new = [doc.Objects.AddCurve(outline, attrs)]
    if sa > 0:
        new.append(doc.Objects.AddCurve(seg, attrs))  # лінія шва
    if mark:
        new.append(doc.Objects.AddCurve(mark, attrs))
    label = u"%s%d  H=%g" % (PREFIX, n, h)
    te = Rhino.Geometry.TextEntity.Create(label, label_frame(seg, pocket_side(seg, toward, h, normal, tol, rigid), normal),
                                          text_style(doc, h / 4.0), False, 0, 0)
    te.TextHorizontalAlignment = Rhino.DocObjects.TextHorizontalAlignment.Center
    te.TextVerticalAlignment = Rhino.DocObjects.TextVerticalAlignment.Middle
    new.append(doc.Objects.AddText(te, attrs))
    for o in new:
        for k, v in (("H", h), ("Trim", trim), ("SA", sa), ("Notch", int(notch)), ("Rigid", int(rigid))):
            rs.SetUserText(o, "TP_" + k, "%g" % v)
    rs.AddObjectsToGroup(new, rs.AddGroup())
    doc.Views.Redraw()
    return label


def layer():
    if not rs.IsLayer("Parts"):
        rs.AddLayer("Parts")
    if not rs.IsLayer(LAYER):
        rs.AddLayer("Pockets", parent="Parts")
    return LAYER


def next_number(lay):
    """Наступний номер після найбільшого TP<n>, що вже є в шарі."""
    nums = [0]
    for o in rs.ObjectsByLayer(lay) or []:
        m = re.match(PREFIX + r"(\d+)\b", rs.TextObjectText(o) if rs.IsText(o) else "")
        if m:
            nums.append(int(m.group(1)))
    return max(nums) + 1


def inward(panel, edge, normal):
    """Точка всередині панелі біля середини ребра (ребро йде за обходом панелі)."""
    tm = edge.Domain.Mid
    t = edge.TangentAt(tm)
    cw = panel.ClosedCurveOrientation(normal) == CurveOrientation.Clockwise
    out = Vector3d.CrossProduct(normal, t) if cw else Vector3d.CrossProduct(t, normal)
    out.Unitize()
    return edge.PointAt(tm) - out


def ask(gp):
    """Клік біля ребра з опціями W, H, Trim, SA, Notch, Rigid, Angle. (точка, значення) або None."""
    get = sc.sticky.get
    w = Rhino.Input.Custom.OptionDouble(get(STICKY + "_w", 2000.0), 0.0, 1e7)
    h = Rhino.Input.Custom.OptionDouble(get(STICKY + "_h", 130.0), 0.001, 1e6)
    trim = Rhino.Input.Custom.OptionDouble(get(STICKY + "_trim", 50.0), 0.0, 1e6)
    sa = Rhino.Input.Custom.OptionDouble(get(STICKY + "_sa", 10.0), 0.0, 1e6)
    notch = Rhino.Input.Custom.OptionToggle(get(STICKY + "_notch", True), "No", "Yes")
    rigid = Rhino.Input.Custom.OptionToggle(get(STICKY + "_rigid", False), "No", "Yes")
    angle = Rhino.Input.Custom.OptionDouble(get("CopriZip_angle", 30.0), 1.0, 179.0)  # спільний із CopriZip
    gp.AddOptionDouble("W", w)
    gp.AddOptionDouble("H", h)
    gp.AddOptionDouble("Trim", trim)
    gp.AddOptionDouble("SA", sa)
    gp.AddOptionToggle("Notch", notch)
    gp.AddOptionToggle("Rigid", rigid)
    gp.AddOptionDouble("Angle", angle)
    while True:
        r = gp.Get()
        vals = (w.CurrentValue, h.CurrentValue, trim.CurrentValue, sa.CurrentValue, notch.CurrentValue, rigid.CurrentValue)
        for k, v in zip(("_w", "_h", "_trim", "_sa", "_notch", "_rigid"), vals):
            sc.sticky[STICKY + k] = v
        sc.sticky["CopriZip_angle"] = angle.CurrentValue
        if r == Rhino.Input.GetResult.Option:
            continue
        return (gp.Point(), vals + (angle.CurrentValue,)) if r == Rhino.Input.GetResult.Point else None


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
    n = next_number(LAYER)
    made = 0
    while True:
        gp = Rhino.Input.Custom.GetPoint()
        gp.SetCommandPrompt(u"Клікни біля ребра під карман (W=0 — усе ребро; Enter — кінець)")
        gp.AcceptNothing(True)
        got = ask(gp)
        if got is None:
            break
        click, (w, h, trim, sa, notch, rigid, angle) = got
        res = pick_edge(panel, click, angle, tol)
        if not isinstance(res, tuple):
            print(u"Пропущено: " + res)
            continue
        edge = res[3]
        if 0 < edge.GetLength() <= w:
            print(u"W %g ≥ довжини ребра %.1f — карман на все ребро" % (w, edge.GetLength()))
        toward = inward(panel, edge, normal)
        res = pocket(edge, toward, w, h, trim, sa, notch, normal, tol, rigid)
        if not isinstance(res, tuple):
            print(u"Пропущено: " + res)
            continue
        res = res + (toward,)
        label = add_pocket(doc, res, h, trim, sa, notch, n, attrs, normal, tol, rigid)
        print(label)
        n += 1
        made += 1
    print(u"Карманів: %d → %s" % (made, LAYER))


if __name__ == "__main__":
    main()
