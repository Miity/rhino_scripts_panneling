# -*- coding: utf-8 -*-
import rhinoscriptsyntax as rs
import scriptcontext as sc
import Rhino.Geometry as rg
import math

def smart_explode_ultimate():
    # 1. Запит кривих
    curve_ids = rs.GetObjects("Виберіть криві для 'Розумного розбиття'", rs.filter.curve, preselect=True)
    if not curve_ids: return

    # 2. Запит кута
    angle_deg = rs.GetReal("Пороговий кут розбиття (в градусах)", 45.0, 0.0, 180.0)
    if angle_deg is None: return
    
    # 3. НОВИЙ ПАРАМЕТР: Довжина сміттєвих сегментів
    noise_len = rs.GetReal("Ігнорувати 'мікро-сходинки' коротші за (в одиницях файлу)", 1.0, 0.0)
    if noise_len is None: return

    threshold_rad = math.radians(angle_deg)
    rs.EnableRedraw(False)
    curves_added = []
    
    for crv_id in curve_ids:
        crv = rs.coercecurve(crv_id)
        if not crv: continue
        
        segments = crv.DuplicateSegments()
        if not segments or len(segments) <= 1: continue
            
        # --- ФІЛЬТРАЦІЯ МІКРО-ШУМУ ---
        # Залишаємо тільки ті сегменти, які довші за заданий поріг
        valid_segments = []
        for seg in segments:
            if seg.GetLength() > noise_len:
                valid_segments.append(seg)
                
        # Якщо після очистки не залишилось що аналізувати - пропускаємо
        if len(valid_segments) <= 1: continue
            
        split_params = []
        start_index = 0 if crv.IsClosed else 1
        
        # Аналізуємо лише стабільні, довгі сегменти
        for i in range(start_index, len(valid_segments)):
            prev_seg = valid_segments[i - 1] 
            curr_seg = valid_segments[i]
            
            # Беремо вектори на кінці попереднього і початку наступного ВАЛІДНОГО сегмента
            v1 = prev_seg.TangentAt(prev_seg.Domain.Max)
            v2 = curr_seg.TangentAt(curr_seg.Domain.Min)
            
            # Захист: якщо вектор нульовий, беремо загальний напрямок відрізка
            if v1.IsZero: v1 = prev_seg.PointAtEnd - prev_seg.PointAtStart
            if v2.IsZero: v2 = curr_seg.PointAtEnd - curr_seg.PointAtStart
            
            if v1.IsZero or v2.IsZero: continue
                
            angle = rg.Vector3d.VectorAngle(v1, v2)
            
            # Якщо глобальний кут перевищує поріг
            if angle > (threshold_rad + 1e-5):
                # Знаходимо точку розбиття
                rc, t = crv.ClosestPoint(curr_seg.PointAtStart)
                if rc:
                    # Захист для відкритих кривих від розрізу на кінцях
                    if not crv.IsClosed:
                        if abs(t - crv.Domain.Min) < 1e-5 or abs(t - crv.Domain.Max) < 1e-5:
                            continue
                    split_params.append(t)
        
        # Фізичне розбиття
        if split_params:
            split_params = list(set(split_params))
            split_results = crv.Split(split_params)
            
            if split_results and len(split_results) > 0:
                attr = sc.doc.Objects.Find(crv_id).Attributes
                for sc_crv in split_results:
                    new_id = sc.doc.Objects.AddCurve(sc_crv, attr)
                    curves_added.append(new_id)
                rs.DeleteObject(crv_id)
                
    rs.EnableRedraw(True)
    if curves_added:
        rs.SelectObjects(curves_added)

if __name__ == "__main__":
    smart_explode_ultimate()