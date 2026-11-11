# -*- coding: utf-8 -*-
"""Undo of the last click inside a running click loop (option Undo in the click prompt).
Rhino's own Undo only works after the command ends; this takes back one click at a time while it runs.
Per click (step): objects added during it (runtime serial number ≥ the one at start()), objects changed
(geometry + attributes before the first change in the step), objects deleted (undeleted, same id).
Undo of a step: added objects deleted, deleted undeleted, changed ones get back their geometry and attributes
(layer, groups, UserText).

Use in a click loop:
    steps = Steps()
    pt = click_options(gp, [("W", "MyScript_w", 60.0, 0.0, 1e6), ("Layout", "MyScript_layout", True)])   # the prompt: see click_options
    if pt == UNDO: steps.undo(); <re-read state, numbers>; continue
    steps.start()                                      # before each click's changes
    steps.change(id) BEFORE Replace / ModifyAttributes / group or UserText change; steps.delete(id) to delete
"""
import Rhino
import scriptcontext as sc

UNDO = "undo"  # what a click prompt returns for the Undo option
CHANGED = "changed"  # ... for a list option: the caller builds its prompt / options again and asks once more


def click_options(gp, options=(), style=None, undo=True):
    """One click of a click loop: prompt gp (a GetPoint, its text already set) with options, asked until a point or
    Enter. Undo is added first (it keeps the letter U), then options in their order, Style last:
      (name, sticky key, default, lowest, highest) — a number (an int default — a whole number);
      (name, sticky key, True / False) — a Yes / No switch;
      (name, sticky key, [values], default index) — a list: the picked index goes to sticky, returns CHANGED;
      "Name" — a plain option: returns its name.
    Numbers and switches are read from sc.sticky[key] (default when not there yet) and written back after every Get —
    the caller reads them from sc.sticky. style — called for the option Style (pick a text style).
    Returns a point, UNDO, CHANGED, the name of a plain option, or None (Enter / Esc)."""
    C = Rhino.Input.Custom
    gp.ClearCommandOptions()
    i_undo = gp.AddOption("Undo") if undo else -1
    held, lists, plain = [], {}, {}
    for o in options:
        if not isinstance(o, (tuple, list)):
            plain[gp.AddOption(o)] = o
            continue
        name, key, default = o[0], o[1], o[2]
        if isinstance(default, (tuple, list)):
            lists[gp.AddOptionList(name, default, sc.sticky.get(key, o[3] if len(o) > 3 else 0))] = key
            continue
        if isinstance(default, bool):
            value = C.OptionToggle(sc.sticky.get(key, default), "No", "Yes")
            gp.AddOptionToggle(name, value)
        elif isinstance(default, int):
            value = C.OptionInteger(sc.sticky.get(key, default), o[3], o[4])
            gp.AddOptionInteger(name, value)
        else:
            value = C.OptionDouble(sc.sticky.get(key, default), o[3], o[4])
            gp.AddOptionDouble(name, value)
        held.append((key, value))
    i_style = gp.AddOption("Style") if style else -1
    while True:
        res = gp.Get()
        for key, value in held:
            sc.sticky[key] = value.CurrentValue
        if res != Rhino.Input.GetResult.Option:
            return gp.Point() if res == Rhino.Input.GetResult.Point else None
        i = gp.OptionIndex()
        if i == i_undo:
            return UNDO
        if i in plain:
            return plain[i]
        if i in lists:
            sc.sticky[lists[i]] = gp.Option().CurrentListOptionIndex
            return CHANGED
        if i == i_style:
            style()


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
