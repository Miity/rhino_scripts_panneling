# -*- coding: utf-8 -*-
"""Interactive holding tabs for closed, coplanar Rhino curves (6/7/8).

Toolbar: ! _-RunPythonScript "/Users/dmytro/Documents/Rhino/scripts/analysis/AddCutTabs.py"
Orange = existing no-cut intervals; green = candidate; red = invalid candidate.
Click a marked interval to remove it. Move selects a tab then its new position.
Enter commits; Esc cancels the preview. Width and Undo are command options.
Width is arc length in document units, not a curve parameter or chord distance.
Changed originals are hidden after success; new cuts retain original attributes.
The final selection includes untouched input curves for Export Selected.
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


def tab_intervals(length, centers, width, tolerance):
    """Return (cut intervals, gap intervals), with decreasing pairs at seam.

    All coordinates are arc lengths. Reject overlaps and residual cuts no
    longer than document tolerance. No interval is silently clipped/merged.
    This part is independent of Rhino and is tested outside its UI.
    """
    values = [length, width, tolerance] + list(centers)
    if any(math.isnan(v) or math.isinf(v) for v in values):
        raise ValueError(u'Розміри повинні бути скінченними числами.')
    if tolerance <= 0 or width <= 2 * tolerance:
        raise ValueError(u'Ширина має бути більшою за подвійний допуск документа.')
    if length <= width + tolerance:
        raise ValueError(u'Перемичка завелика для цього контуру.')
    if not centers:
        return [(0.0, length)], []
    locations = sorted(c % length for c in centers)
    for i, c in enumerate(locations):
        following = locations[(i + 1) % len(locations)]
        separation = following - c if i + 1 < len(locations) else following + length - c
        if separation - width <= tolerance:
            raise ValueError(u'Перемички перекриваються або залишають надто короткий різ.')
    half = width * 0.5
    gaps = [((c - half) % length, (c + half) % length) for c in locations]
    cuts = []
    for i, gap in enumerate(gaps):
        next_gap = gaps[(i + 1) % len(gaps)]
        cuts.append((gap[1], next_gap[0]))
    return cuts, gaps


def arc_distance(a, b, length):
    delta = abs(a - b) % length
    return min(delta, length - delta)


def parameter_at_length(curve, length):
    if length <= 0:
        return curve.Domain.T0
    if length >= curve.GetLength():
        return curve.Domain.T1
    success, parameter = curve.LengthParameter(length)
    if not success:
        raise ValueError(u'Не вдалося відміряти довжину вздовж кривої.')
    return parameter


def trim_arc(curve, interval, tolerance):
    a, b = interval
    ta = parameter_at_length(curve, a)
    tb = parameter_at_length(curve, b)
    part = curve.Trim(ta, tb)
    expected = b - a if b > a else curve.GetLength() - a + b
    if (part is None or not part.IsValid or part.IsClosed or
            abs(part.GetLength() - expected) > tolerance):
        if part is not None:
            part.Dispose()
        raise ValueError(u'Не вдалося точно розділити контур. Оригінал збережено.')
    return part


def dispose_curves(curves):
    for curve in curves:
        curve.Dispose()


def closest_location(records, point, viewport):
    best = None
    for i, record in enumerate(records):
        curve = record['curve']
        ok, t = curve.ClosestPoint(point)
        if not ok:
            continue
        on_curve = curve.PointAt(t)
        screen_a, screen_b = viewport.WorldToClient(point), viewport.WorldToClient(on_curve)
        pixels = math.hypot(screen_a.X - screen_b.X, screen_a.Y - screen_b.Y)
        if pixels > 14.0 or (best is not None and pixels >= best[0]):
            continue
        if t <= curve.Domain.T0:
            position = 0.0
        else:
            position = curve.GetLength(Rhino.Geometry.Interval(curve.Domain.T0, t))
        best = (pixels, i, position % record['length'])
    return None if best is None else (best[1], best[2])


def existing_tab(records, centers, location, width, tolerance):
    index, position = location
    for j, center in enumerate(centers[index]):
        if arc_distance(position, center, records[index]['length']) <= width * 0.5 + tolerance:
            return index, j
    return None


if Rhino is not None:
    class TabPreview(Rhino.Display.DisplayConduit):
        def __init__(self):
            super(TabPreview, self).__init__()
            self.parts = []

        def rebuild(self, records, centers, width, tolerance):
            parts = []
            try:
                for i, record in enumerate(records):
                    if not centers[i]:
                        continue
                    cuts, gaps = tab_intervals(record['length'], centers[i], width, tolerance)
                    for gap in gaps:
                        parts.append(trim_arc(record['curve'], gap, tolerance))
            except Exception:
                dispose_curves(parts)
                raise
            dispose_curves(self.parts)
            self.parts = parts

        def PostDrawObjects(self, event):
            for part in self.parts:
                event.Display.DrawCurve(part, Color.DarkOrange, 5)

        def clear(self):
            self.Enabled = False
            dispose_curves(self.parts)
            self.parts = []


def snapshot(centers, width):
    return [list(items) for items in centers], width


def validate_all(records, centers, width, tolerance):
    for i, record in enumerate(records):
        if centers[i]:
            tab_intervals(record['length'], centers[i], width, tolerance)


def preview_candidate(event, records, centers, width, tolerance, moving):
    location = closest_location(records, event.CurrentPoint, event.Viewport)
    if location is None:
        return
    ci, position = location
    tab = existing_tab(records, centers, location, width, tolerance)
    candidate = [list(items) for items in centers]
    if moving is not None:
        candidate[moving[0]].pop(moving[1])
    elif tab is not None:
        return  # The orange interval is the click-to-remove target.
    candidate[ci].append(position)
    try:
        validate_all(records, candidate, width, tolerance)
        gap = ((position - width * 0.5) % records[ci]['length'],
               (position + width * 0.5) % records[ci]['length'])
        part = trim_arc(records[ci]['curve'], gap, tolerance)
        try:
            event.Display.DrawCurve(part, Color.LimeGreen, 6)
        finally:
            part.Dispose()
    except ValueError:
        point = records[ci]['curve'].PointAt(parameter_at_length(records[ci]['curve'], position))
        event.Display.DrawPoint(point, Rhino.Display.PointStyle.X, 7, Color.Red)


def edit_tabs(records, plane, width, tolerance):
    centers = [[] for record in records]
    history = []
    preview = TabPreview()
    preview.Enabled = True
    moving = None
    select_move = False
    try:
        while True:
            count = sum(len(items) for items in centers)
            if select_move:
                prompt = u'Клікніть помаранчеву перемичку для переміщення (Enter — назад)'
            elif moving is not None:
                prompt = u'Клікніть нове місце перемички (Enter — назад)'
            else:
                prompt = (u'Перемичок: %d, ширина: %g. Клік — додати/прибрати; '
                          u'Enter — застосувати; Esc — скасувати' % (count, width))
            gp = Rhino.Input.Custom.GetPoint()
            gp.SetCommandPrompt(prompt)
            gp.AcceptNothing(True)
            gp.Constrain(plane, False)
            options = {}
            if not select_move and moving is None:
                for name in ('Move', 'Width', 'Undo', 'Clear'):
                    options[gp.AddOption(name)] = name

            def draw(sender, event):
                if not select_move:
                    preview_candidate(event, records, centers, width, tolerance, moving)

            gp.DynamicDraw += draw
            try:
                result = gp.Get()
                point = gp.Point() if result == Rhino.Input.GetResult.Point else None
                option = options.get(gp.OptionIndex()) if result == Rhino.Input.GetResult.Option else None
                view = gp.View() if result == Rhino.Input.GetResult.Point else None
            finally:
                gp.DynamicDraw -= draw
                gp.Dispose()
            if result == Rhino.Input.GetResult.Cancel:
                return None
            if result == Rhino.Input.GetResult.Nothing:
                if select_move or moving is not None:
                    select_move, moving = False, None
                    continue
                return centers, width
            if result == Rhino.Input.GetResult.Option:
                if option == 'Move':
                    if count:
                        select_move = True
                    else:
                        print(u'Спочатку додайте перемичку.')
                elif option == 'Width':
                    new_width = rs.GetReal(u'Ширина перемички вздовж контуру (одиниці документа)',
                                           width, 2.0 * tolerance)
                    if new_width is not None:
                        try:
                            if new_width <= 2.0 * tolerance:
                                raise ValueError(u'Ширина має перевищувати подвійний допуск.')
                            validate_all(records, centers, new_width, tolerance)
                            preview.rebuild(records, centers, new_width, tolerance)
                            history.append(snapshot(centers, width))
                            width = new_width
                        except ValueError as error:
                            print(error)
                elif option == 'Undo' and history:
                    centers, width = history.pop()
                    preview.rebuild(records, centers, width, tolerance)
                elif option == 'Clear' and count:
                    history.append(snapshot(centers, width))
                    centers = [[] for record in records]
                    preview.rebuild(records, centers, width, tolerance)
                sc.doc.Views.Redraw()
                continue
            if point is None:
                return None
            viewport = view.ActiveViewport if view is not None else sc.doc.Views.ActiveView.ActiveViewport
            location = closest_location(records, point, viewport)
            if location is None:
                print(u'Клікніть ближче до одного з вибраних контурів.')
                continue
            tab = existing_tab(records, centers, location, width, tolerance)
            if select_move:
                if tab is None:
                    print(u'Клікніть помаранчеву ділянку.')
                else:
                    moving, select_move = tab, False
                continue
            candidate, unused_width = snapshot(centers, width)
            ci, position = location
            if moving is not None:
                candidate[moving[0]].pop(moving[1])
                candidate[ci].append(position)
            elif tab is not None:
                candidate[tab[0]].pop(tab[1])
            else:
                candidate[ci].append(position)
            try:
                validate_all(records, candidate, width, tolerance)
                preview.rebuild(records, candidate, width, tolerance)
            except ValueError as error:
                print(error)
                continue
            history.append(snapshot(centers, width))
            centers = candidate
            moving = None
            sc.doc.Views.Redraw()
    finally:
        preview.clear()
        sc.doc.Views.Redraw()


def commit_tabs(records, centers, width, tolerance):
    """Prepare first, then add all cuts, then hide sources; roll back on error."""
    prepared = []
    changed = []
    selected = []
    try:
        for i, record in enumerate(records):
            if not centers[i]:
                selected.append(record['id'])
                continue
            cuts, gaps = tab_intervals(record['length'], centers[i], width, tolerance)
            changed.append(record['id'])
            for interval in cuts:
                part = trim_arc(record['curve'], interval, tolerance)
                attrs = sc.doc.Objects.FindId(record['id']).Attributes.Duplicate()
                attrs.SetUserString('CutTabs.SourceId', str(record['id']))
                attrs.SetUserString('CutTabs.Width', repr(width))
                attrs.SetUserString('CutTabs.Centers', ','.join(repr(c) for c in centers[i]))
                prepared.append((part, attrs))
        if not changed:
            return None
        undo_record = sc.doc.BeginUndoRecord('AddCutTabs')
        added, hidden = [], []
        try:
            for part, attrs in prepared:
                object_id = sc.doc.Objects.AddCurve(part, attrs)
                if object_id == System.Guid.Empty:
                    raise RuntimeError(u'Не вдалося додати ділянку різу.')
                added.append(object_id)
            for source_id in changed:
                if not sc.doc.Objects.Hide(source_id, True):
                    raise RuntimeError(u'Не вдалося приховати оригінал.')
                hidden.append(source_id)
            selected.extend(added)
            rs.UnselectAllObjects()
            rs.SelectObjects(selected)
        except Exception:
            for object_id in hidden:
                sc.doc.Objects.Show(object_id, True)
            for object_id in added:
                sc.doc.Objects.Delete(object_id, True)
            raise
        finally:
            if undo_record:
                sc.doc.EndUndoRecord(undo_record)
        return len(changed), len(added)
    finally:
        dispose_curves([part for part, attrs in prepared])
        sc.doc.Views.Redraw()


HELP = u"""Опції:
  Move — перемістити перемичку
  Width — ширина перемички
  Undo — скасувати останню дію
  Clear — прибрати всі перемички"""  # друкується на старті — видно під полями опцій


def main():
    print(HELP)
    ids = rs.GetObjects(u'Виберіть замкнені контури для перемичок',
                        rs.filter.curve, preselect=True)
    if not ids:
        return
    tolerance = sc.doc.ModelAbsoluteTolerance
    records = []
    completed = False
    try:
        plane = None
        for object_id in ids:
            source = sc.doc.Objects.FindId(object_id)
            if source is None or source.IsLocked or source.IsReference:
                raise ValueError(u'Виберіть звичайні редаговані криві.')
            curve = rs.coercecurve(object_id).DuplicateCurve()
            records.append({'id': object_id, 'curve': curve, 'length': curve.GetLength()})
            if not curve.IsValid or not curve.IsClosed or not curve.IsPlanar(tolerance):
                raise ValueError(u'Потрібні коректні замкнені плоскі криві.')
            if plane is None:
                success, plane = curve.TryGetPlane(tolerance)
                if not success:
                    raise ValueError(u'Не вдалося визначити площину контуру.')
            if not curve.IsInPlane(plane, tolerance):
                raise ValueError(u'Усі вибрані контури мають лежати в одній площині.')
        if sc.doc.ModelUnitSystem == getattr(Rhino.UnitSystem, 'None'):
            default_width = max(tolerance * 10.0, 1.0)
            print(u'Документ без одиниць: ширину буде виміряно в одиницях креслення.')
        else:
            # 0.5 mm is only an editable starting value, not a material prescription.
            factor = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters,
                                               sc.doc.ModelUnitSystem)
            default_width = max(0.5 * factor, tolerance * 10.0)
        width = rs.GetReal(u'Ширина перемички вздовж контуру (одиниці документа)',
                           default_width, tolerance * 2.0)
        if width is None:
            return
        if width <= tolerance * 2.0:
            raise ValueError(u'Ширина має перевищувати подвійний допуск документа.')
        rs.UnselectAllObjects()
        print(u'Помаранчеве — не різати. Зелене — нова перемичка. '
              u'Move — перемістити; Width — ширина; Undo — назад; Clear — очистити.')
        result = edit_tabs(records, plane, width, tolerance)
        if result is None:
            print(u'Скасовано.')
            return
        centers, width = result
        summary = commit_tabs(records, centers, width, tolerance)
        if summary is None:
            print(u'Перемичок немає; контури не змінено.')
            return
        completed = True
        print(u'Створено перемичок: %d; оброблено контурів: %d; ділянок різу: %d.' %
              (sum(len(items) for items in centers), summary[0], summary[1]))
        print(u'Результат вибрано разом із рештою початково вибраних контурів. '
              u'Експортуйте вибране. Оригінали оброблених кривих приховані; '
              u'Undo скасовує операцію, Show повертає оригінали (вони накладатимуться на різ).')
    except Exception as error:
        print(u'Перемички: %s' % error)
    finally:
        if not completed:
            rs.UnselectAllObjects()
            rs.SelectObjects(ids)
        dispose_curves([record['curve'] for record in records])
        sc.doc.Views.Redraw()


if __name__ == '__main__':
    main()
