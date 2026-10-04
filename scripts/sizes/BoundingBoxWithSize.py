import rhinoscriptsyntax as rs
import scriptcontext as sc
import Rhino, System

"""Adds a ghosted bounding box for selected objects with annotation dots
for XYZ sizes.  volume reported on command line.
Script written by Mitch Heynick - version 13.06.15"""

def SetGhostedObjDisplayModeAllViewports(objIDs):
    if isinstance(objIDs,System.Guid): objIDs=[objIDs]
    modeName="Ghosted"
    dModes = Rhino.Display.DisplayModeDescription.GetDisplayModes()
    modeNames=[dMode.LocalName for dMode in dModes if not dMode.PipelineLocked]
    
    index=-1
    for i in range(len(modeNames)):
        if modeName==modeNames[i]:
            index=i ; break
    if index==-1: return
        
    vIDs=[view.ActiveViewportID for view in sc.doc.Views]
    for vID in vIDs:
        for objID in objIDs:
            objRef=sc.doc.Objects.Find(objID)
            attr = objRef.Attributes
            attr.SetDisplayModeOverride(dModes[i], vID)
            sc.doc.Objects.ModifyAttributes(objID, attr, False)
    
def BoundingBoxWithSize():
    msg="Pick objects for bounding box"
    err_msg="Bounding box creation failed."
    objs = rs.GetObjects(msg,preselect=True)
    if not objs: return    
    bb = rs.BoundingBox(objs)
    if not bb: 
        print err_msg ; return
    
    prec = sc.doc.DistanceDisplayPrecision
    tol = sc.doc.ModelAbsoluteTolerance
    sc.doc.ModelUnitSystem
    unit_sys = sc.doc.ModelUnitSystem
    unit_name=sc.doc.GetUnitSystemName(True,False,True,True)
    
    XL = bb[1].DistanceTo(bb[0])
    YL = bb[3].DistanceTo(bb[0])
    ZL = bb[4].DistanceTo(bb[0])
    
    #2d/3d/NoD check
    isX = 1 ; isY = 1 ; isZ = 1
    if XL < tol: isX = 0
    if YL < tol: isY = 0
    if ZL < tol: isZ = 0
    if isX+isY+isZ < 2:
        #two or more 0 length sides
        print(err_msg) ; return 
    
    vol=False
    if XL < tol: av_calc = YL * ZL
    elif YL < tol: av_calc = XL * ZL
    elif ZL < tol: av_calc = XL * YL
    else:
        av_calc = XL * YL * ZL
        vol=True
        
    XMpt = (bb[0]+bb[1])/2
    YMpt = (bb[0]+bb[3])/2
    ZMpt = (bb[0]+bb[4])/2
    
    str_xl = "" ; str_yl = "" ; str_zl = ""
    if isX > 0: str_xl = "X " + str(round(XL, prec))        
    if isY > 0: str_yl = "Y " + str(round(YL, prec))
    if isZ > 0: str_zl = "Z " + str(round(ZL, prec))
        
    rs.EnableRedraw(False)
    group=[]
    if vol :
        group.append(rs.AddBox(bb))
        rs.SurfaceIsocurveDensity(group[0], -1)
        SetGhostedObjDisplayModeAllViewports(group[0])
    else:
        if not isX: 
            group.append(rs.AddPolyline([bb[0], bb[3], bb[7], bb[4], bb[0]]))
        elif not isY:
            group.append(rs.AddPolyline([bb[0], bb[1], bb[5], bb[4], bb[0]]))
        elif not isZ:
            group.append(rs.AddPolyline([bb[0], bb[1], bb[2], bb[3], bb[0]]))
    
    if isX: group.append(rs.AddTextDot(str_xl, XMpt))
    if isY: group.append(rs.AddTextDot(str_yl, YMpt))
    if isZ: group.append(rs.AddTextDot(str_zl, ZMpt))

    grp_name = rs.AddGroup()
    rs.AddObjectsToGroup(group, grp_name)
    rs.ObjectColor(group, System.Drawing.Color.Black)
    
    if vol:
        desc="volume" ; sqcu="cubic "
    else:
        desc="area" ; sqcu="sq. "
    AV = " || {}: {} {}{}".format(desc,round(av_calc, prec),sqcu,unit_name)

    if str_xl: str_xl = " | " + str_xl
    if str_yl: str_yl = " | " + str_yl
    if str_zl: str_zl = " | " + str_zl
    print "Bounding box size:{}{}{}{}".format(str_xl,str_yl,str_zl,AV)
BoundingBoxWithSize()