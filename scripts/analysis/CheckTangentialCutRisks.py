# -*- coding: utf-8 -*-
"""Mark likely paper-cutting trouble spots on closed DXF polylines.

Run in Rhino 6/7/8 with _EditPythonScript or _ScriptEditor. Select the cut
polylines, then choose thresholds. Geometry is never changed. Text dots go
on four CUT_RISK:: layers, so each class can be hidden independently.

Distances are in the document's model units. The DXF itself may have no
unit declaration; verify the imported scale before trusting millimetres.
"""

import math

try:
    import Rhino
    import rhinoscriptsyntax as rs
    import scriptcontext as sc
except ImportError:
    Rhino = rs = sc = None


def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def point_to_segment(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    denominator = dx * dx + dy * dy
    if denominator == 0.0:
        return distance(p, a), a, 0.0
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx +
                            (p[1] - a[1]) * dy) / denominator))
    q = (a[0] + t * dx, a[1] + t * dy)
    return distance(p, q), q, t


def segment_gap(a, b, c, d):
    """Distance, closest points, and fractional positions on both segments."""
    r = (b[0] - a[0], b[1] - a[1])
    s = (d[0] - c[0], d[1] - c[1])
    den = r[0] * s[1] - r[1] * s[0]
    if abs(den) > 1e-12 * distance(a, b) * distance(c, d):
        ac = (c[0] - a[0], c[1] - a[1])
        t = (ac[0] * s[1] - ac[1] * s[0]) / den
        u = (ac[0] * r[1] - ac[1] * r[0]) / den
        if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
            p = (a[0] + t * r[0], a[1] + t * r[1])
            return 0.0, p, p, t, u
    options = []
    for p, t in ((a, 0.0), (b, 1.0)):
        gap, q, u = point_to_segment(p, c, d)
        options.append((gap, p, q, t, u))
    for q, u in ((c, 0.0), (d, 1.0)):
        gap, p, t = point_to_segment(q, a, b)
        options.append((gap, p, q, t, u))
    return min(options, key=lambda item: item[0])


def signed_area(points):
    return 0.5 * sum(points[i][0] * points[(i + 1) % len(points)][1] -
                     points[(i + 1) % len(points)][0] * points[i][1]
                     for i in range(len(points)))


def contour_data(points, tolerance):
    """Return polyline measurements, omitting a repeated closing vertex."""
    points = list(points)
    if len(points) > 1 and distance(points[0], points[-1]) <= tolerance:
        points.pop()
    if len(points) < 3:
        return None
    segments = []
    accumulated = 0.0
    for index, a in enumerate(points):
        b = points[(index + 1) % len(points)]
        length = distance(a, b)
        if length <= tolerance:
            continue
        segments.append((a, b, index, accumulated, length))
        accumulated += length
    if len(segments) < 3:
        return None
    return {'points': points, 'segments': segments,
            'perimeter': accumulated, 'area': abs(signed_area(points))}


def distinct_regions(cells, min_gap):
    """Keep the closest point in each connected patch of nearby hits."""
    by_owner = {}
    for (owner, ix, iy), hit in cells.items():
        by_owner.setdefault(owner, {})[(ix, iy)] = hit
    result = {}
    for owner, owner_cells in by_owner.items():
        remaining = set(owner_cells)
        region_index = 0
        while remaining:
            start = next(iter(remaining))
            remaining.remove(start)
            queue = [start]
            best = owner_cells[start]
            while queue:
                ix, iy = queue.pop()
                here = owner_cells[(ix, iy)]
                if here[0] < best[0]:
                    best = here
                midpoint = ((here[1][0] + here[2][0]) * 0.5,
                            (here[1][1] + here[2][1]) * 0.5)
                for dx in (-2, -1, 0, 1, 2):
                    for dy in (-2, -1, 0, 1, 2):
                        neighbor = (ix + dx, iy + dy)
                        if neighbor not in remaining:
                            continue
                        other = owner_cells[neighbor]
                        other_midpoint = ((other[1][0] + other[2][0]) * 0.5,
                                          (other[1][1] + other[2][1]) * 0.5)
                        if distance(midpoint, other_midpoint) <= 2.0 * min_gap:
                            remaining.remove(neighbor)
                            queue.append(neighbor)
            result[(owner, region_index)] = best
            region_index += 1
    return result


def scan(contours, min_gap, min_area, turn_degrees):
    """Return distinct close regions, small contours, and sharp turns."""
    segments = []
    for curve_index, contour in enumerate(contours):
        for a, b, vertex_index, arclength, length in contour['segments']:
            segments.append((curve_index, vertex_index, a, b,
                             arclength, length,
                             min(a[0], b[0]), max(a[0], b[0]),
                             min(a[1], b[1]), max(a[1], b[1])))
    segments.sort(key=lambda item: item[6])
    between_cells = {}
    within_cells = {}
    for first_index, first in enumerate(segments):
        ca, ia, a, b, sa, la, x0, x1, y0, y1 = first
        for second in segments[first_index + 1:]:
            cb, ib, c, d, sb, lb, xx0, xx1, yy0, yy1 = second
            if xx0 > x1 + min_gap:
                break
            if yy0 > y1 + min_gap or yy1 < y0 - min_gap:
                continue
            if ca == cb and ia == ib:
                continue
            gap, p, q, t, u = segment_gap(a, b, c, d)
            if gap >= min_gap:
                continue
            if ca == cb:
                perimeter = contours[ca]['perimeter']
                along = abs((sa + t * la) - (sb + u * lb))
                along = min(along, perimeter - along)
                # Nearby samples of a smooth boundary are not a narrow neck.
                if along <= 2.0 * min_gap:
                    continue
                owner = ca
                target = within_cells
            else:
                owner = (min(ca, cb), max(ca, cb))
                target = between_cells
            midpoint = ((p[0] + q[0]) * 0.5,
                        (p[1] + q[1]) * 0.5)
            key = (owner, int(math.floor(midpoint[0] / min_gap)),
                   int(math.floor(midpoint[1] / min_gap)))
            if key not in target or gap < target[key][0]:
                target[key] = (gap, p, q)

    small = []
    turns = []
    for curve_index, contour in enumerate(contours):
        if contour['area'] < min_area:
            small.append((curve_index, contour['area']))
        points = contour['points']
        count = len(points)
        for index, p in enumerate(points):
            before, after = points[index - 1], points[(index + 1) % count]
            vx, vy = p[0] - before[0], p[1] - before[1]
            wx, wy = after[0] - p[0], after[1] - p[1]
            lengths = math.hypot(vx, vy) * math.hypot(wx, wy)
            if lengths <= 0.0:
                continue
            cosine = max(-1.0, min(1.0, (vx * wx + vy * wy) / lengths))
            angle = math.degrees(math.acos(cosine))
            if angle >= turn_degrees:
                turns.append((curve_index, index, angle, p))
    return (distinct_regions(between_cells, min_gap),
            distinct_regions(within_cells, min_gap), small, turns)


def layer(name, color):
    path = 'CUT_RISK::' + name
    if not rs.IsLayer('CUT_RISK'):
        rs.AddLayer('CUT_RISK')
    if not rs.IsLayer(path):
        rs.AddLayer(name, color, parent='CUT_RISK')
    # A repeated scan replaces only dots made by this script.
    for object_id in rs.ObjectsByLayer(path) or []:
        if rs.GetUserText(object_id, 'CUT_RISK_GENERATED') == '1':
            rs.DeleteObject(object_id)
    return path


def dot(message, xy, z, layer_name):
    object_id = rs.AddTextDot(message, (xy[0], xy[1], z))
    if object_id:
        rs.SetUserText(object_id, 'CUT_RISK_GENERATED', '1')
        rs.ObjectLayer(object_id, layer_name)


def main():
    ids = rs.GetObjects(u'Select closed cut polylines',
                        rs.filter.curve, preselect=True)
    if not ids:
        return
    tolerance = sc.doc.ModelAbsoluteTolerance
    mm_to_doc = Rhino.RhinoMath.UnitScale(
        Rhino.UnitSystem.Millimeters, sc.doc.ModelUnitSystem)
    if mm_to_doc <= 0.0:
        mm_to_doc = 1.0
    min_gap = rs.GetReal(u'Minimum allowed gap (document units)',
                         5.0 * mm_to_doc, tolerance)
    if min_gap is None:
        return
    min_area = rs.GetReal(u'Minimum part area (sq. document units)',
                          25.0 * mm_to_doc * mm_to_doc, 0.0)
    if min_area is None:
        return
    turn_degrees = rs.GetReal(u'Mark knife turns from (degrees)',
                              120.0, 0.0, 180.0)
    if turn_degrees is None:
        return

    contours, valid_ids, z_values = [], [], []
    skipped = 0
    for object_id in ids:
        if not rs.IsPolyline(object_id) or not rs.IsCurveClosed(object_id):
            skipped += 1
            continue
        vertices = rs.PolylineVertices(object_id)
        if not vertices:
            skipped += 1
            continue
        z = vertices[0].Z
        if any(abs(p.Z - z) > tolerance for p in vertices):
            skipped += 1
            continue
        contour = contour_data([(p.X, p.Y) for p in vertices], tolerance)
        if contour is None:
            skipped += 1
            continue
        contours.append(contour)
        valid_ids.append(object_id)
        z_values.append(z)
    if not contours:
        print(u'No closed planar polylines found.')
        return
    if max(z_values) - min(z_values) > tolerance:
        print(u'Contours lie at different Z heights; check the cut plane.')
        return

    between, within, small, turns = scan(contours, min_gap,
                                          min_area, turn_degrees)
    rs.EnableRedraw(False)
    try:
        gap_layer = layer('01_between_contours', (220, 40, 40))
        neck_layer = layer('02_narrow_in_contour', (230, 120, 20))
        area_layer = layer('03_small_area', (150, 50, 180))
        turn_layer = layer('04_sharp_turn', (40, 100, 220))
        z = z_values[0]
        for key, (gap, p, q) in sorted(between.items()):
            xy = ((p[0] + q[0]) * 0.5, (p[1] + q[1]) * 0.5)
            dot('G %.2f' % gap, xy, z, gap_layer)
        for key, (gap, p, q) in sorted(within.items()):
            xy = ((p[0] + q[0]) * 0.5, (p[1] + q[1]) * 0.5)
            dot('W %.2f' % gap, xy, z, neck_layer)
        for index, area in small:
            points = contours[index]['points']
            xy = (sum(p[0] for p in points) / len(points),
                  sum(p[1] for p in points) / len(points))
            dot('A %.1f' % area, xy, z, area_layer)
        for curve_index, vertex_index, angle, p in turns:
            dot('T %.0f' % angle, p, z, turn_layer)
    finally:
        rs.EnableRedraw(True)
    print(u'Contours checked: %d; skipped: %d.' %
          (len(contours), skipped))
    print(u'Gaps between contours: %d; narrow spots in a contour: %d; '
          u'small parts: %d; sharp turns: %d.' %
          (len(between), len(within), len(small), len(turns)))
    print(u'G — between contours; W — width within one contour; '
          u'A — area; T — knife turn. Original curves unchanged.')


if __name__ == '__main__':
    main()
