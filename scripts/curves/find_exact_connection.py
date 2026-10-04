# -*- coding: utf-8 -*-
"""
Senior Computational Designer Tool
Calculates the exact contact point on a curve from a selected point with a locked length.
Works directly in Rhino Document.
"""

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc

def find_exact_connection():
    # 1. Отримуємо допуск документа (System Absolute Tolerance)
    tolerance = sc.doc.ModelAbsoluteTolerance
    
    # 2. Вибір цільової кривої
    curve_id = rs.GetCurveObject("Виберіть цільову криву для другого з'єднання", preselect=False)
    if not curve_id: 
        print("Помилка: Криву не вибрано.")
        return
    curve_geom = rs.coercecurve(curve_id[0])
    
    # 3. Вибір першої фіксованої точки (P1)
    point_id = rs.GetObject("Виберіть точку першого з'єднання (P1)", filter=1, preselect=False)
    if not point_id:
        # Якщо точку не вибрано в документі, пропонуємо її просто вказати кліком
        p1 = rs.GetPoint("Точку не вибрано. Вкажіть точку P1 кліком у просторі")
    else:
        p1 = rs.PointCoordinates(point_id)
        
    if not p1:
        print("Помилка: Точку P1 не визначено.")
        return
        
    # 4. Введення довжини лінії (L)
    length = rs.GetReal("Введіть точну довжину лінії (L) в одиницях документа", minimum=0.001)
    if not length:
        print("Помилка: Некоректна довжина.")
        return

    # 5. Математичний розрахунок через RhinoCommon
    p1_3d = Rhino.Geometry.Point3d(p1[0], p1[1], p1[2])
    sphere = Rhino.Geometry.Sphere(p1_3d, length)
    sphere_brep = sphere.ToBrep()
    
    if not sphere_brep:
        print("Помилка побудови сфери обмежувача.")
        return
        
    # Розрахунок перетину NURBS-кривої та Brep-сфери
    rc, _, intersection_points = Rhino.Geometry.Intersect.Intersection.CurveBrep(
        curve_geom, 
        sphere_brep, 
        tolerance
    )
    
    # 6. Генерація геометрії в документі
    if rc and intersection_points:
        sc.doc.Objects.UnselectAll()
        
        # Вимикаємо оновлення екрану для прискорення побудови
        rs.EnableRedraw(False)
        
        created_lines = []
        for pt in intersection_points:
            # Додаємо точку перетину в Rhino Doc
            pt_id = sc.doc.Objects.AddPoint(pt)
            # Будуємо лінію фіксованої довжини
            line_geom = Rhino.Geometry.Line(p1_3d, pt)
            line_id = sc.doc.Objects.AddLine(line_geom)
            
            created_lines.append(line_id)
            # Підсвічуємо створені об'єкти
            rs.SelectObject(line_id)
            rs.SelectObject(pt_id)
            
        rs.EnableRedraw(True)
        print("Успішно! Знайдено варіантів з'єднання: {}. Створені лінії виділено.".format(len(created_lines)))
    else:
        print("Помилка геометричного аналізу: Крива знаходиться поза радіусом досяжності {} одиниць від точки P1.".format(length))

if __name__ == "__main__":
    find_exact_connection()