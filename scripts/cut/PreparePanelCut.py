# -*- coding: utf-8 -*-
"""Prepare outside cuts and unique, separate internal lines from panel linework.

Run in Rhino 6/7/8 with _EditPythonScript or _ScriptEditor. Step 1: select
coplanar polylines or lines (panels, seam strips, loose edges, duplicates are
fine); every area they enclose counts as a panel, and each separate
group of touching areas becomes its own panel. Step 2: select what belongs on ``int``
(Enter = nothing). Step 3: select what belongs on ``ink`` (Enter = every other
visible curve and text). Only curves lying inside the panels (texts by their
centre) are used in steps 2 and 3;
everything else is left untouched. Panels are hidden after success and can be restored with
Rhino's _Show command. Each panel becomes one outside loop on ``cut``; every
other edge goes once, touching pieces joined into one curve, to ``int`` if
any panel line is picked in step 2, otherwise to ``ink``. Steps 2 and 3 move
the selected objects as they are (no copy). Each outside must be a simple loop
(panels touching at a single point are rejected).

The script creates internal lines first and the outside loops last. The order
in which a plotter cuts layers must still be set in the plotter software.
"""

import math

try:
    import Rhino
    import System
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
except ImportError:
    Rhino = System = rs = sc = None


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def along(a, b, t):
    return (a[0] + (b[0] - a[0]) * t,
            a[1] + (b[1] - a[1]) * t)


def parameter(p, a, b):
    d = sub(b, a)
    return dot(sub(p, a), d) / dot(d, d)


def point_segment_distance(p, a, b):
    return dist(p, along(a, b, max(0.0, min(1.0, parameter(p, a, b)))))


def signed_area(poly):
    return 0.5 * sum(cross(poly[i], poly[(i + 1) % len(poly)])
                     for i in range(len(poly)))


def inside(p, poly):
    """Even-odd point containment; callers keep p away from the boundary."""
    hit = False
    x, y = p
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        if (a[1] > y) != (b[1] > y):
            x_cross = a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if x_cross > x:
                hit = not hit
    return hit


def unique_parameters(values, length, tol):
    values = sorted(max(0.0, min(1.0, value)) for value in values)
    out = []
    for value in values:
        if not out or (value - out[-1]) * length > tol:
            out.append(value)
    if out:
        out[0], out[-1] = 0.0, 1.0
    return out


def split_segments(segments, tol):
    """Split at crossings, T junctions and collinear overlap endpoints."""
    cuts = [[0.0, 1.0] for segment in segments]
    for i in range(len(segments)):
        a, b = segments[i]
        r = sub(b, a)
        lr = dist(a, b)
        for j in range(i + 1, len(segments)):
            c, d = segments[j]
            s = sub(d, c)
            ls = dist(c, d)
            den = cross(r, s)
            if abs(den) <= tol * lr * ls / max(lr, ls):
                if abs(cross(sub(c, a), r)) > tol * lr:
                    continue
                for point in (c, d):
                    t = parameter(point, a, b)
                    if -tol / lr <= t <= 1.0 + tol / lr:
                        cuts[i].append(t)
                for point in (a, b):
                    u = parameter(point, c, d)
                    if -tol / ls <= u <= 1.0 + tol / ls:
                        cuts[j].append(u)
            else:
                ac = sub(c, a)
                t = cross(ac, s) / den
                u = cross(ac, r) / den
                if (-tol / lr <= t <= 1.0 + tol / lr and
                        -tol / ls <= u <= 1.0 + tol / ls):
                    cuts[i].append(t)
                    cuts[j].append(u)
    pieces = []
    for index, (a, b) in enumerate(segments):
        ts = unique_parameters(cuts[index], dist(a, b), tol)
        for k in range(len(ts) - 1):
            p, q = along(a, b, ts[k]), along(a, b, ts[k + 1])
            if dist(p, q) > tol:
                pieces.append((p, q))
    return pieces


def canonical_edges(pieces, tol):
    """Share one node for coincident points and one edge for overlaps."""
    nodes = []

    def node_id(point):
        for i, other in enumerate(nodes):
            if dist(point, other) <= tol:
                return i
        nodes.append(point)
        return len(nodes) - 1

    edges = {}
    for a, b in pieces:
        i, j = node_id(a), node_id(b)
        if i != j:
            key = (min(i, j), max(i, j))
            edges[key] = True
    return nodes, sorted(edges)


def faces(nodes, edges, tol):
    """Bounded faces of the planar line graph as CCW point lists, and the
    nodes left after trimming dangling ends."""
    adjacency = {}
    for i, j in edges:
        adjacency.setdefault(i, set()).add(j)
        adjacency.setdefault(j, set()).add(i)
    # Dangling ends enclose nothing.
    loose = [i for i in adjacency if len(adjacency[i]) < 2]
    while loose:
        i = loose.pop()
        for j in adjacency.pop(i, ()):
            adjacency[j].discard(i)
            if len(adjacency[j]) == 1:
                loose.append(j)
    order = {}
    for i, around in adjacency.items():
        order[i] = sorted(around, key=lambda j: math.atan2(nodes[j][1] - nodes[i][1],
                                                           nodes[j][0] - nodes[i][0]))
    seen = set()
    out = []
    for i in order:
        for j in order[i]:
            if (i, j) in seen:
                continue
            face = []
            u, v = i, j
            while (u, v) not in seen:
                seen.add((u, v))
                face.append(nodes[u])
                around = order[v]
                u, v = v, around[(around.index(u) - 1) % len(around)]
            if signed_area(face) > tol * tol:
                out.append(face)
    return out, set(adjacency)


def occupancy_sides(a, b, polygons, segments, tol):
    length = dist(a, b)
    middle = along(a, b, 0.5)
    # The offset must stay inside the nearest open face of the linework.
    nearest = None
    for c, d in segments:
        distance = point_segment_distance(middle, c, d)
        if distance > tol and (nearest is None or distance < nearest):
            nearest = distance
    step = length * 0.25
    if nearest is not None:
        step = min(step, nearest * 0.25)
    if step <= tol:
        raise ValueError(u"Надто близькі лінії або короткий сегмент відносно допуску документа.")
    normal = (-(b[1] - a[1]) / length, (b[0] - a[0]) / length)
    left = (middle[0] + normal[0] * step, middle[1] + normal[1] * step)
    right = (middle[0] - normal[0] * step, middle[1] - normal[1] * step)
    return (any(inside(left, poly) for poly in polygons),
            any(inside(right, poly) for poly in polygons))


def classify(nodes, edges, polygons, segments, tol, closed_nodes):
    outside, internal = [], []
    for i, j in edges:
        if i not in closed_nodes or j not in closed_nodes:
            # A dangling piece bounds nothing, so it is never an outside edge.
            internal.append((i, j))
            continue
        in_left, in_right = occupancy_sides(nodes[i], nodes[j], polygons, segments, tol)
        if in_left != in_right:
            outside.append((i, j))
        elif in_left:
            internal.append((i, j))
        else:
            raise ValueError(u"Не вдалося визначити призначення сегмента.")
    return outside, internal


def trace_boundary_loops(nodes, edges):
    adjacency = {}
    for i, j in edges:
        adjacency.setdefault(i, []).append(j)
        adjacency.setdefault(j, []).append(i)
    if not edges or any(len(neighbors) != 2 for neighbors in adjacency.values()):
        raise ValueError(u"Зовнішній контур має розрив або неоднозначне з'єднання.")
    unseen = set(adjacency)
    loops = []
    while unseen:
        start = min(unseen)
        loop = [start]
        previous = None
        current = start
        while True:
            neighbors = adjacency[current]
            nxt = neighbors[0] if neighbors[0] != previous else neighbors[1]
            if nxt == start:
                break
            if nxt in loop:
                raise ValueError(u"Зовнішній контур сам себе торкається.")
            loop.append(nxt)
            previous, current = current, nxt
        unseen.difference_update(loop)
        loops.append(loop)
    return loops


def simplify_loop(nodes, loop, tol):
    result = []
    for k, index in enumerate(loop):
        a = nodes[loop[k - 1]]
        b = nodes[index]
        c = nodes[loop[(k + 1) % len(loop)]]
        ab, bc = sub(b, a), sub(c, b)
        if abs(cross(ab, bc)) > tol * (dist(a, b) + dist(b, c)) or dot(ab, bc) <= 0:
            result.append(index)
    if len(result) < 3:
        raise ValueError(u"Зовнішній контур вироджений.")
    return result


def prepare(segments, tol):
    """Return (nodes, one closed loop of node ids per panel, unique internal edges, faces)."""
    nodes, edges = canonical_edges(split_segments(segments, tol), tol)
    polygons, closed_nodes = faces(nodes, edges, tol)
    if not polygons:
        raise ValueError(u"Лінії не утворюють жодного замкненого контуру.")
    outside, internal = classify(nodes, edges, polygons, segments, tol, closed_nodes)
    # Every enclosed area is a face, so each outside loop is a separate panel.
    loops = [simplify_loop(nodes, loop, tol) for loop in trace_boundary_loops(nodes, outside)]
    return nodes, loops, internal, polygons


DUPLICATE_MM = 0.5  # copies closer than this are one cut line


def unique_polylines(ids):
    """Polylines of the selection, keeping one of each near-duplicate group."""
    gap = DUPLICATE_MM * Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters,
                                                   sc.doc.ModelUnitSystem)
    curves = []
    for object_id in ids:
        curve = rs.coercecurve(object_id)
        ok, polyline = curve.TryGetPolyline() if curve is not None else (False, None)
        if not ok or polyline is None:
            raise ValueError(u"У виборі є крива, яка не є полілінією або лінією.")
        curves.append((polyline.Count, curve, polyline))
    kept = []
    # ponytail: pairwise check, fine for hundreds of curves.
    for _, curve, polyline in sorted(curves, key=lambda item: item[0]):
        ends = (curve.PointAtStart, curve.PointAtEnd)
        if not any(abs(curve.GetLength() - other.GetLength()) <= 2 * gap and
                   min(ends[0].DistanceTo(other.PointAtStart) + ends[1].DistanceTo(other.PointAtEnd),
                       ends[0].DistanceTo(other.PointAtEnd) + ends[1].DistanceTo(other.PointAtStart)) <= gap and
                   Rhino.Geometry.Curve.GetDistancesBetweenCurves(curve, other, gap * 0.01)[1] <= gap
                   for other, _ in kept):
            kept.append((curve, polyline))
    return [list(polyline) for _, polyline in kept]


def get_plane_and_segments(ids, tol):
    chains = unique_polylines(ids)
    ok, plane = Rhino.Geometry.Plane.FitPlaneToPoints([p for chain in chains for p in chain])
    if ok != Rhino.Geometry.PlaneFitResult.Success:
        raise ValueError(u"Не вдалося визначити площину фігур.")
    segments = []
    for chain in chains:
        flat = []
        for point in chain:
            vector = point - plane.Origin
            if abs(vector * plane.ZAxis) > tol:
                raise ValueError(u"Вибрані фігури не лежать в одній площині.")
            flat.append((vector * plane.XAxis, vector * plane.YAxis))
        segments.extend((a, b) for a, b in zip(flat, flat[1:]) if dist(a, b) > tol)
    return plane, segments


def point_covered(p, polygons, tol):
    """True if p is inside a panel or on its boundary."""
    for poly in polygons:
        if inside(p, poly):
            return True
        if any(point_segment_distance(p, poly[i], poly[(i + 1) % len(poly)]) <= tol
               for i in range(len(poly))):
            return True
    return False


def curve_samples(curve):
    ok, polyline = curve.TryGetPolyline()
    if ok and polyline is not None:
        points = list(polyline)
        mids = [(points[i] + points[i + 1]) * 0.5 for i in range(len(points) - 1)]
        return points + mids
    params = curve.DivideByCount(20, True)
    return [curve.PointAt(t) for t in params] if params else []


def only_inside(ids, plane, polygons, tol):
    """Keep curves lying fully in the panel plane and inside the panels.

    Texts and other annotations count by the centre of their bounding box.
    """
    keep = []
    for object_id in ids:
        curve = rs.coercecurve(object_id)
        if curve is not None:
            points = curve_samples(curve)
        else:
            box = rs.coercegeometry(object_id).GetBoundingBox(True)
            points = [box.Center] if box.IsValid else []
        if points and all(abs((p - plane.Origin) * plane.ZAxis) <= tol and point_covered(
                ((p - plane.Origin) * plane.XAxis, (p - plane.Origin) * plane.YAxis),
                polygons, tol) for p in points):
            keep.append(object_id)
    return keep


MARKS = 4 | 512  # rs.filter.curve | rs.filter.annotation: lines and texts


def main():
    ids = rs.GetObjects(u"Крок 1: виберіть лінії панелей (полілінії, лінії, смуги шва)", rs.filter.curve,
                        preselect=True, select=False)
    if not ids:
        return
    tol = sc.doc.ModelAbsoluteTolerance
    try:
        plane, segments = get_plane_and_segments(ids, tol)
        nodes, loops, internal, polygons = prepare(segments, tol)
    except ValueError as error:
        print(u"Не створено розкрій: {0}".format(error))
        return

    panel_ids = set(ids)
    picked_int = rs.GetObjects(
        u"Крок 2: виберіть лінії для int (Enter - немає; лінії панелі тут - її внутрішні лінії на int)",
        MARKS, preselect=False, select=False) or []
    # Inner panel edges follow the panel lines: int only when picked in step 2.
    edge_layer = "int" if panel_ids.intersection(picked_int) else "ink"
    to_int = only_inside([i for i in picked_int if i not in panel_ids], plane, polygons, tol)
    to_ink = rs.GetObjects(u"Крок 3: виберіть лінії для ink (Enter - усе, що залишилось у панелях)",
                           MARKS, preselect=False, select=False)
    if not to_ink:
        to_ink = rs.ObjectsByType(MARKS, select=False, state=1) or []
    taken = panel_ids.union(to_int)
    to_ink = only_inside([i for i in to_ink if i not in taken], plane, polygons, tol)

    if not rs.IsLayer("int"):
        rs.AddLayer("int")
    for name in ("cut", "ink"):
        if not rs.IsLayer(name):
            rs.AddLayer(name)

    def world(index):
        x, y = nodes[index]
        return plane.PointAt(x, y)

    created = []
    try:
        # Each shared edge once; touching pieces are joined so arcs stay one curve.
        lines = [Rhino.Geometry.LineCurve(world(i), world(j)) for i, j in internal]
        for curve in Rhino.Geometry.Curve.JoinCurves(lines, tol) if lines else []:
            object_id = sc.doc.Objects.AddCurve(curve)
            if object_id == System.Guid.Empty:
                raise RuntimeError(u"Не вдалося додати внутрішню лінію.")
            rs.ObjectLayer(object_id, edge_layer)
            created.append(object_id)
        edge_count = len(created)
        for loop in loops:
            perimeter = [world(index) for index in loop]
            perimeter.append(perimeter[0])
            object_id = rs.AddPolyline(perimeter)
            if not object_id:
                raise RuntimeError(u"Не вдалося додати зовнішню полілінію.")
            rs.ObjectLayer(object_id, "cut")
            created.append(object_id)
    except Exception as error:
        for object_id in created:
            rs.DeleteObject(object_id)
        print(u"Не створено розкрій: {0}".format(error))
        return
    for object_id in to_int:
        rs.ObjectLayer(object_id, "int")
    for object_id in to_ink:
        rs.ObjectLayer(object_id, "ink")
    created.extend(to_int + to_ink)
    # Keep editable sources without leaving their duplicate edges visible.
    rs.HideObjects(ids)
    rs.UnselectAllObjects()
    rs.SelectObjects(created)
    sc.doc.Views.Redraw()
    print(u"Готово: панелей (контурів на cut): {3}, внутрішніх ліній панелей на {4}: {0}, "
          u"переміщено на int: {1}, на ink: {2}. "
          u"Вихідні фігури приховано; результат виділено для Export Selected."
          .format(edge_count, len(to_int), len(to_ink), len(loops), edge_layer))


def _self_check():
    def rectangle(x0, y0, x1, y1):
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]

    def pick(segments, tol):
        nodes, loops, internal, _ = prepare(segments, tol)
        return [[nodes[i] for i in loop] for loop in loops], internal

    def closed(*polys):
        return [(poly[i], poly[(i + 1) % len(poly)]) for poly in polys
                for i in range(len(poly))]

    (loop,), internal = pick(closed(rectangle(0, 0, 10, 10),
                             rectangle(10, 0, 20, 10)), 1e-6)
    assert len(loop) == 4 and len(internal) == 1
    assert abs(signed_area(loop)) == 200
    (loop,), internal = pick(closed(rectangle(0, 0, 10, 10),
                             rectangle(10, 0, 20, 5),
                             rectangle(10, 5, 20, 10)), 1e-6)
    assert len(loop) == 4 and len(internal) == 3
    (loop,), internal = pick(closed(rectangle(0, 0, 10, 10),
                             rectangle(0, 0, 10, 10)), 1e-6)
    assert len(loop) == 4 and not internal
    # Enclosed gap: its edges go to int with the shared edges.
    (loop,), internal = pick(closed(
        rectangle(0, 0, 30, 10), rectangle(0, 10, 10, 20),
        rectangle(20, 10, 30, 20), rectangle(0, 20, 30, 30)), 1e-6)
    assert len(loop) == 4 and len(internal) == 8
    # Seam strips as loose lines, notched corners, duplicate panel edges.
    panel = closed(rectangle(0, 0, 10, 10))
    strips = [((0, 0), (0, -1)), ((0, -1), (10, -1)), ((10, -1), (10, 0)),
              ((10, 0), (11, 0)), ((11, 0), (11, 10)), ((11, 10), (10, 10))]
    (loop,), internal = pick(panel + panel + strips, 1e-6)
    assert len(loop) == 6  # notch at (10, 0)
    assert abs(signed_area(loop)) == 120
    assert len(internal) == 2  # panel edges under the two strips
    # A dangling line inside the panel is internal.
    (loop,), internal = pick(panel + [((2, 2), (5, 5))], 1e-6)
    assert len(loop) == 4 and len(internal) == 1
    # A line crossing the edge by a hair leaves a tiny stub outside: still fine.
    (loop,), internal = pick(panel + [((5, 5), (10.000003, 5))], 1e-6)
    assert len(loop) == 4 and abs(signed_area(loop)) == 100
    frame, _ = faces(*(canonical_edges(split_segments(closed(
        rectangle(0, 0, 30, 10), rectangle(0, 10, 10, 20),
        rectangle(20, 10, 30, 20), rectangle(0, 20, 30, 30)), 1e-6), 1e-6) + (1e-6,)))
    assert point_covered((5, 15), frame, 1e-6)       # inside a panel
    assert point_covered((10, 15), frame, 1e-6)      # on a shared edge
    assert point_covered((15, 15), frame, 1e-6)      # enclosed gap counts as panel
    assert not point_covered((40, 5), frame, 1e-6)   # outside
    # Separate panels: one loop each.
    loops, internal = pick(closed(rectangle(0, 0, 10, 10), rectangle(20, 0, 30, 10)), 1e-6)
    assert len(loops) == 2 and not internal
    for bad in ([((0, 0), (10, 0)), ((10, 0), (10, 10))],
                closed(rectangle(0, 0, 10, 10), rectangle(10, 10, 20, 20))):
        try:
            prepare(bad, 1e-6)
        except ValueError:
            pass
        else:
            raise AssertionError("bad input was accepted")
    print("self-check ok")


if __name__ == "__main__":
    if Rhino is None:
        _self_check()
    else:
        main()
