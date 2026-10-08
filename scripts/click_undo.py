# -*- coding: utf-8 -*-
"""Undo of the last click inside a running click loop (option Undo in the click prompt).
Rhino's own Undo only works after the command ends; this takes back one click at a time while it runs.
Per click (step): objects added during it (runtime serial number ≥ the one at start()), objects changed
(geometry + attributes before the first change in the step), objects deleted (undeleted, same id).
Undo of a step: added objects deleted, deleted undeleted, changed ones get back their geometry and attributes
(layer, groups, UserText).

Use in a click loop:
    steps = Steps()
    i_undo = gp.AddOption("Undo")                      # FIRST option in the click prompt (keeps U); on it return UNDO
    if click == UNDO: steps.undo(); <re-read state, numbers>; continue
    steps.start()                                      # before each click's changes
    steps.change(id) BEFORE Replace / ModifyAttributes / group or UserText change; steps.delete(id) to delete
"""
import Rhino
import scriptcontext as sc

UNDO = "undo"  # what a click prompt returns for the Undo option


class Steps(object):
    def __init__(self, doc=None):
        self.doc = doc or sc.doc
        self.steps = []

    def start(self):
        if self.steps:
            self.close(self.steps[-1])
        self.steps.append({"sn": Rhino.DocObjects.RhinoObject.NextRuntimeSerialNumber, "old": {}, "gone": []})

    def change(self, oid):
        """Call BEFORE changing the object (geometry, attributes, groups); the first state in the step is kept."""
        old = self.steps[-1]["old"]
        if oid not in old:
            o = self.doc.Objects.FindId(oid)
            if o is not None:
                old[oid] = (o.Geometry.Duplicate(), o.Attributes.Duplicate())

    def delete(self, oid):
        o = self.doc.Objects.FindId(oid)
        if o is not None:
            self.change(oid)
            self.doc.Objects.Delete(o, True)
            self.steps[-1]["gone"].append(o)

    def close(self, step):
        """Fixes the objects added during the step (serial ≥ its start; a replaced object gets a new serial too —
        those are in "old"). Done when the next step starts, before any undo restores objects (new serials)."""
        if "new" not in step:
            step["new"] = [o.Id for o in self.doc.Objects
                           if o.RuntimeSerialNumber >= step["sn"] and o.Id not in step["old"]]

    def undo(self):
        """Takes back the last step that changed something. False — nothing to undo."""
        while self.steps:
            step = self.steps.pop()
            self.close(step)
            new = step["new"]
            if new or step["old"] or step["gone"]:
                break
        else:
            print(u"Nothing to undo")
            return False
        for i in new:
            self.doc.Objects.Delete(i, True)
        for o in step["gone"]:
            self.doc.Objects.Undelete(o)
        for oid, (geo, attrs) in step["old"].items():
            self.doc.Objects.Replace(oid, geo)
            self.doc.Objects.ModifyAttributes(oid, attrs, True)
        self.doc.Views.Redraw()
        return True
