# -*- coding: utf-8 -*-
"""Undo of the last click inside a running click loop (option Undo in the click prompt).
Rhino's own Undo only works after the command ends; this takes back one click at a time while it runs.
Per click (step): objects created, objects changed (geometry + attributes before the first change in the step),
objects deleted (kept and undeleted, same id). Undo of a step: created objects deleted, deleted undeleted,
changed ones get back their geometry and attributes (layer, groups, UserText).

Use in a click loop:
    steps = Steps()
    i_undo = gp.AddOption("Undo")                      # in the click prompt; on it return UNDO
    if click == UNDO: steps.undo(); <re-read state>; continue
    steps.start()                                      # before each click's changes
    steps.created(ids) / steps.change(id) before Replace / ModifyAttributes / group change / steps.delete(id)
"""
import scriptcontext as sc

UNDO = "undo"  # what a click prompt returns for the Undo option


class Steps(object):
    def __init__(self, doc=None):
        self.doc = doc or sc.doc
        self.steps = []

    def start(self):
        self.steps.append({"new": [], "old": {}, "gone": []})

    def created(self, ids):
        self.steps[-1]["new"] += [i for i in ids if i]

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

    def undo(self):
        """Takes back the last step that changed something. False — nothing to undo."""
        while self.steps and not any(self.steps[-1].values()):
            self.steps.pop()
        if not self.steps:
            print(u"Nothing to undo")
            return False
        step = self.steps.pop()
        for i in step["new"]:
            self.doc.Objects.Delete(i, True)
        for o in step["gone"]:
            self.doc.Objects.Undelete(o)
        for oid, (geo, attrs) in step["old"].items():
            self.doc.Objects.Replace(oid, geo)
            self.doc.Objects.ModifyAttributes(oid, attrs, True)
        self.doc.Views.Redraw()
        return True
