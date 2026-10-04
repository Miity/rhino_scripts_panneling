# -*- coding: utf-8 -*-
import rhinoscriptsyntax as rs

def convert_to_polyline_keep_layer():
    # Отримуємо виділені об'єкти
    selected_objs = rs.SelectedObjects()
    
    if not selected_objs:
        print("Будь ласка, виберіть криві перед запуском.")
        return

    # Налаштування допуску
    tolerance = 0.1

    rs.EnableRedraw(False)
    
    for obj in selected_objs:
        if rs.IsCurve(obj):
            # 1. Запам'ятовуємо шар оригінальної кривої
            original_layer = rs.ObjectLayer(obj)
            
            # 2. Конвертуємо в полілінію
            polyline = rs.ConvertCurveToPolyline(obj, angle_tolerance=5, tolerance=tolerance)
            
            if polyline:
                # 3. Присвоюємо новій полілінії шар оригіналу
                rs.ObjectLayer(polyline, original_layer)
                
                # 4. Видаляємо оригінал
                rs.DeleteObject(obj)
    
    rs.EnableRedraw(True)
    print("Конвертацію завершено. Шари збережено.")

if __name__ == "__main__":
    convert_to_polyline_keep_layer()