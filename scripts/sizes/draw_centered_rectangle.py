# -*- coding: utf-8 -*-
import rhinoscriptsyntax as rs

def draw_centered_rectangle_on_cplane():
    # Параметри геометрії (в одиницях документу)
    width = 1340.0
    height = 6657.973
    
    # Отримання активного CPlane
    cplane = rs.ViewCPlane()
    
    # Запит точки у користувача
    center_pt = rs.GetPoint("Вкажіть центр прямокутника", in_plane=True)
    if not center_pt: 
        return
    
    # Перенесення системи координат (CPlane) у вказану точку
    base_plane = rs.MovePlane(cplane, center_pt)
    
    # Обчислення вектора зміщення для кута прямокутника
    shift_vec = base_plane.XAxis * (-width / 2.0) + base_plane.YAxis * (-height / 2.0)
    corner_pt = rs.PointAdd(base_plane.Origin, shift_vec)
    
    # Створення площини для побудови прямокутника
    rect_plane = rs.MovePlane(base_plane, corner_pt)
    
    # Генерація геометрії (NURBS curve)
    rectangle_id = rs.AddRectangle(rect_plane, width, height)
    
    if rectangle_id:
        rs.SelectObject(rectangle_id)
        print("Прямокутник успішно згенеровано.")

if __name__ == "__main__":
    draw_centered_rectangle_on_cplane()