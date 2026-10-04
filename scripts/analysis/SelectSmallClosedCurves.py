# -*- coding: utf-8 -*-
# Вибирає всі замкнені криві, площа яких менша за поріг
# (дрібні контури, які плотер/різак фізично не проріже).
import rhinoscriptsyntax as rs
import scriptcontext as sc


def select_small_closed_curves():
    # Поріг у кв. одиницях документа. 25 мм^2 ~ отвір діаметром 5.6 мм.
    min_area = rs.GetReal("Мінімальна площа, яку ріже плотер (кв. одиниць)", 25.0, 0.0)
    if min_area is None:
        return

    # Працюємо з виділеним, а якщо нічого не вибрано — з усіма кривими документа.
    objs = rs.SelectedObjects() or rs.ObjectsByType(4, select=False)
    if not objs:
        print("Кривих у документі не знайдено.")
        return

    rs.EnableRedraw(False)
    rs.UnselectAllObjects()

    small = []
    for obj in objs:
        if not rs.IsCurveClosed(obj):
            continue
        # Плоскі криві: CurveArea повертає None для неплоских — їх пропускаємо.
        if not rs.IsCurvePlanar(obj, sc.doc.ModelAbsoluteTolerance):
            continue
        area = rs.CurveArea(obj)
        if area and area[0] < min_area:
            small.append(obj)

    rs.SelectObjects(small)
    rs.EnableRedraw(True)
    print("Вибрано {} замкнених кривих з площею < {}.".format(len(small), min_area))


if __name__ == "__main__":
    select_small_closed_curves()
