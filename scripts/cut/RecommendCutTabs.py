# -*- coding: utf-8 -*-
"""Select whole closed contours that are candidates for holding tabs.

Rhino 6/7/8, IronPython 2.7 / CPython 3. No external packages.
Toolbar: ! _-RunPythonScript "/Users/dmytro/Documents/Rhino/scripts/cut/RecommendCutTabs.py"

Red: area below threshold or characteristic width 2*area/perimeter below
threshold. Orange: approximate local interior neck below width threshold.
These are screening rules, not a calibrated model of vacuum or paper stiffness.
Every closed contour is assessed independently; nesting/hole area is not subtracted.
"""
import math
try:
    import Rhino
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
    import System
    from System.Drawing import Color
except ImportError:
    Rhino = rs = sc = System = Color = None

try:
    text_type = unicode
except NameError:
    text_type = str

TAG = 'RecommendCutTabs.Generated'


def distance(a, b):
    return math.hypot(a[0]-b[0], a[1]-b[1])


def polygon_area(points):
    # Translation avoids cancellation for imported DXFs far from the origin.
    ox, oy = points[0]
    return .5 * sum((a[0]-ox)*(b[1]-oy)-(b[0]-ox)*(a[1]-oy)
                    for a, b in zip(points, points[1:]+points[:1]))


def inside(point, polygon):
    x, y = point
    answer = False
    for a, b in zip(polygon, polygon[1:]+polygon[:1]):
        if (a[1] > y) != (b[1] > y):
            if x < a[0] + (y-a[1])*(b[0]-a[0])/(b[1]-a[1]):
                answer = not answer
    return answer


def projection(p, a, b):
    dx, dy = b[0]-a[0], b[1]-a[1]
    t = max(0., min(1., ((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy)))
    return (a[0]+t*dx, a[1]+t*dy), t


def closest_pair(a, b, c, d):
    # Input polygons are checked for self-intersections in Rhino first.
    candidates = []
    for p, t in ((a, 0.), (b, 1.)):
        q, u = projection(p, c, d)
        candidates.append((distance(p, q), p, q, t, u))
    for q, u in ((c, 0.), (d, 1.)):
        p, t = projection(q, a, b)
        candidates.append((distance(p, q), p, q, t, u))
    # Parallel equal-distance solutions include a central witness, so a
    # boundary corner does not conceal a narrow interior strip.
    mid = ((a[0]+b[0])*.5, (a[1]+b[1])*.5)
    q, u = projection(mid, c, d)
    candidates.append((distance(mid, q), mid, q, .5, u))
    return candidates


def local_neck(points, threshold, tolerance):
    """Approximate interior boundary proximity, ignoring short turns.

    Opposing inward normals and interior witnesses reject gaps across empty
    slits. Shortest arc separation must exceed twice the width threshold.
    Returns one narrowest witness; it is not a medial-axis width field.
    """
    points = list(points)
    if distance(points[0], points[-1]) <= tolerance:
        points.pop()
    if len(points) < 3:
        return None
    orientation = 1. if polygon_area(points) > 0 else -1.
    segments = []
    perimeter = 0.
    for a, b in zip(points, points[1:]+points[:1]):
        length = distance(a, b)
        if length == 0:
            continue
        segments.append((a, b, length, perimeter,
                         min(a[0], b[0]), max(a[0], b[0]),
                         min(a[1], b[1]), max(a[1], b[1])))
        perimeter += length
    segments.sort(key=lambda s: s[4])
    best = None
    for i, first in enumerate(segments):
        a, b, la, sa, x0, x1, y0, y1 = first
        for j in range(i+1, len(segments)):
            c, d, lb, sb, xx0, xx1, yy0, yy1 = segments[j]
            if xx0 > x1+threshold:
                break
            if yy0 > y1+threshold or yy1 < y0-threshold:
                continue
            for gap, p, q, t, u in closest_pair(a, b, c, d):
                if gap <= tolerance or gap >= threshold:
                    continue
                if best is not None and gap >= best[0]:
                    continue
                along = abs((sa+t*la)-(sb+u*lb))
                if min(along, perimeter-along) <= 2*threshold:
                    continue
                vx, vy = q[0]-p[0], q[1]-p[1]
                # A connector should enter the polygon at both ends.
                dot_a = orientation*(-(b[1]-a[1])*vx+(b[0]-a[0])*vy)/la
                dot_b = orientation*((d[1]-c[1])*vx-(d[0]-c[0])*vy)/lb
                if dot_a <= tolerance or dot_b <= tolerance:
                    continue
                witnesses = [(p[0]+f*vx, p[1]+f*vy) for f in (.25, .5, .75)]
                if not all(inside(w, points) for w in witnesses):
                    continue
                # Reject a connector that crosses another boundary between
                # the witnesses, including very narrow notches.
                crosses = False
                for e, f in zip(points, points[1:]+points[:1]):
                    ex, ey = f[0]-e[0], f[1]-e[1]
                    den = vx*ey-vy*ex
                    if abs(den) <= 1e-12*gap*max(distance(e, f), tolerance):
                        continue
                    rx, ry = e[0]-p[0], e[1]-p[1]
                    s = (rx*ey-ry*ex)/den
                    v = (rx*vy-ry*vx)/den
                    if tolerance/gap < s < 1-tolerance/gap and 0 <= v <= 1:
                        crosses = True
                        break
                if not crosses:
                    best = (gap, witnesses[1])
    return best


def classify(area, perimeter, min_area, min_width, neck=None):
    characteristic = 2.*area/perimeter
    reasons = []
    if area < min_area:
        reasons.append(('area', area))
    if characteristic < min_width:
        reasons.append(('shape', characteristic))
    if reasons:
        return 'recommended', reasons
    if neck is not None and neck[0] < min_width:
        return 'review', [('neck', neck[0])]
    return None, []


def analyse_curve(curve, min_area, min_width, tolerance, angle_tolerance):
    if not curve.IsValid or not curve.IsClosed or not curve.IsPlanar(tolerance):
        raise ValueError(u'потрібен замкнений плоский контур')
    intersections = Rhino.Geometry.Intersect.Intersection.CurveSelf(curve, tolerance)
    if intersections is not None:
        try:
            if intersections.Count:
                raise ValueError(u'самоперетин або самодотик')
        finally:
            intersections.Dispose()
    amp = Rhino.Geometry.AreaMassProperties.Compute(curve)
    if amp is None:
        raise ValueError(u'не вдалося обчислити площу')
    try:
        area, point = abs(amp.Area), amp.Centroid
    finally:
        amp.Dispose()
    perimeter = curve.GetLength()
    if area <= tolerance*tolerance or perimeter <= tolerance:
        raise ValueError(u'вироджена деталь')
    level, reasons = classify(area, perimeter, min_area, min_width)
    success, plane = curve.TryGetPlane(tolerance)
    if not success:
        raise ValueError(u'не вдалося визначити площину')
    if curve.Contains(point, plane, tolerance) != Rhino.Geometry.PointContainment.Inside:
        point = curve.PointAtNormalizedLength(.5)
    if level is None:
        ok, polyline = curve.TryGetPolyline()
        approximation = None
        try:
            if not ok:
                approximation = curve.ToPolyline(tolerance, angle_tolerance, 0., 0.)
                if approximation is None:
                    raise ValueError(u'не вдалося перевірити локальні звуження')
                ok, polyline = approximation.TryGetPolyline()
            if not ok:
                raise ValueError(u'не вдалося отримати полілінію')
            if polyline.Count > 12000:
                raise ValueError(u'понад 12000 вершин — локальна перевірка пропущена')
            transform = Rhino.Geometry.Transform.PlaneToPlane(plane, Rhino.Geometry.Plane.WorldXY)
            points = []
            for p in polyline:
                local = Rhino.Geometry.Point3d(p)
                local.Transform(transform)
                points.append((local.X, local.Y))
            neck = local_neck(points, min_width, tolerance)
            level, reasons = classify(area, perimeter, min_area, min_width, neck)
            if level == 'review':
                point = plane.PointAt(neck[1][0], neck[1][1])
        finally:
            if approximation is not None:
                approximation.Dispose()
    return {'level': level, 'reasons': reasons, 'point': point,
            'area': area, 'characteristic_width': 2.*area/perimeter}


def annotations(results):
    """Add current markers before removing prior script-owned markers."""
    old = []
    for obj in sc.doc.Objects:
        if obj.Attributes.GetUserString(TAG) == '1':
            old.append(obj.Id)
    parent = 'TABS_CHECK'
    if not rs.IsLayer(parent):
        rs.AddLayer(parent)
    layer_indices = {}
    for name, color in (('Recommended', Color.Crimson), ('Review', Color.DarkOrange)):
        path = parent+'::'+name
        if not rs.IsLayer(path):
            rs.AddLayer(name, color, parent=parent)
        rs.LayerVisible(path, True)
        layer_indices[name.lower()] = sc.doc.Layers.FindByFullPath(path, -1)
    rs.LayerVisible(parent, True)
    added = []
    try:
        for source_id, result in results:
            if result['level'] is None:
                continue
            messages = []
            for kind, value in result['reasons']:
                if kind == 'area':
                    messages.append(u'Мала площа %.2f' % value)
                elif kind == 'shape':
                    messages.append(u'Вузька форма %.2f' % value)
                else:
                    messages.append(u'Звуження ~%.2f' % value)
            attrs = Rhino.DocObjects.ObjectAttributes()
            attrs.LayerIndex = layer_indices[result['level']]
            attrs.SetUserString(TAG, '1')
            attrs.SetUserString('RecommendCutTabs.SourceId', str(source_id))
            attrs.Name = u'Кандидат на перемички: '+u'; '.join(messages)
            dot = Rhino.Geometry.TextDot(u'Перемички?\n'+u'\n'.join(messages), result['point'])
            try:
                oid = sc.doc.Objects.AddTextDot(dot, attrs)
            finally:
                dot.Dispose()
            if oid == System.Guid.Empty:
                raise RuntimeError(u'Не вдалося додати позначку.')
            added.append(oid)
    except Exception:
        for oid in added:
            sc.doc.Objects.Delete(oid, True)
        raise
    failed = sum(not sc.doc.Objects.Delete(oid, True) for oid in old)
    if failed:
        print(u'Не вдалося прибрати старі позначки: %d. Перевірте блокування їхнього шару.' % failed)


def main():
    ids = rs.GetObjects(u'Виберіть контури деталей для перевірки перемичок',
                        rs.filter.curve, preselect=True)
    if not ids:
        return
    tol = sc.doc.ModelAbsoluteTolerance
    factor = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, sc.doc.ModelUnitSystem)
    if sc.doc.ModelUnitSystem == getattr(Rhino.UnitSystem, 'None'):
        factor = 1.
        print(u'Документ без одиниць: усі пороги — в одиницях креслення.')
    area_limit = rs.GetReal(u'Мінімальна площа деталі (кв. одиниці документа)',
                            50.*factor*factor, tol*tol)
    if area_limit is None:
        return
    width_limit = rs.GetReal(u'Поріг вузької форми / звуження (одиниці документа)',
                             max(3.*factor, 10.*tol), 10.*tol)
    if width_limit is None:
        return
    results, skipped = [], []
    for index, oid in enumerate(ids):
        if sc.escape_test(False):
            print(u'Перевірку скасовано.')
            return
        if index % 20 == 0:
            rs.Prompt(u'Перевірка деталей: %d / %d' % (index+1, len(ids)))
            Rhino.RhinoApp.Wait()
        obj = sc.doc.Objects.FindId(oid)
        if obj is None or not isinstance(obj.Geometry, Rhino.Geometry.Curve):
            continue
        try:
            result = analyse_curve(obj.Geometry, area_limit, width_limit,
                                   tol, sc.doc.ModelAngleToleranceRadians)
            results.append((oid, result))
        except Exception as error:
            skipped.append((oid, text_type(error)))
    if not results:
        print(u'Немає придатних контурів. Пропущено: %d.' % len(skipped))
        for oid, reason in skipped[:8]:
            print(u'%s: %s' % (oid, reason))
        return
    annotations(results)
    candidates = [oid for oid, result in results if result['level'] is not None]
    rs.UnselectAllObjects()
    if candidates:
        rs.SelectObjects(candidates)
    sc.doc.Views.Redraw()
    primary = sum(result['level'] == 'recommended' for oid, result in results)
    review = sum(result['level'] == 'review' for oid, result in results)
    print(u'Перевірено: %d. Червоні кандидати: %d; помаранчеві для огляду: %d; '
          u'пропущено: %d.' % (len(results), primary, review, len(skipped)))
    print(u'Виділено цілі контури кандидатів. Можна запускати AddCutTabs. '
          u'Площа — у кв. одиницях; ширини — в одиницях документа. '
          u'Вузька форма = 2*площа/периметр, це показник форми, а не мінімальна ширина.')
    if skipped:
        print(u'Пропущені об’єкти не вважаються перевіреними:')
        for oid, reason in skipped[:8]:
            print(u'%s: %s' % (oid, reason))


if __name__ == '__main__':
    main()
