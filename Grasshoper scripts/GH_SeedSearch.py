# -*- coding: utf-8 -*-
"""SeedSearch — GhPython component for autonest_v2.gh.

Tries OpenNest2 seeds one after another and keeps the layout that takes the
least material along X; among the shortest (within Tol) — the smallest
bounding box area. OpenNest2 runs its generations over many solutions, so
Galapagos can't score it; this component waits for each result ("fit …").

Inputs:
    Geo     : Geo output of OpenNest, Tree access (only to be solved when it changes;
              the layout is read from OpenNest itself)
    Run     : Boolean Toggle — True starts a new search, False stops it
    From    : first seed (default 1)
    Count   : how many seeds (default 50)
    Minutes : time limit, 0 — none
    Tol     : cm — lengths within Tol count as equally short (default 1)
Outputs:
    Seed    : best seed (set on the Seed slider at the end)
    L       : its length along X, cm
    A       : its bounding box area, m²
    Table   : "seed  L cm  A m²" per tried seed, best first
"""


def pick(results, tol):
    """(seed, length, area) list → best one: shortest within tol, then least area."""
    if not results:
        return None
    short = min(r[1] for r in results)
    return min((r for r in results if r[1] <= short + tol), key=lambda r: (r[2], r[1]))


def table(results, tol):
    best = pick(results, tol)
    rows = sorted(results, key=lambda r: (r[1], r[2]))
    rows.remove(best)
    return ["%d  %.1f cm  %.3f m2" % r for r in [best] + rows]


if "ghenv" in globals():
    import time
    import System
    import Rhino
    import scriptcontext as sc
    import Grasshopper

    comp = ghenv.Component
    gd = comp.OnPingDocument()
    key = "SeedSearch_%s" % comp.InstanceGuid
    st = sc.sticky.get(key)

    From = int(From) if From is not None else 1
    Count = int(Count) if Count else 50
    Minutes = float(Minutes) if Minutes else 0.0
    Tol = float(Tol) if Tol is not None else 1.0
    cm = Rhino.RhinoMath.UnitScale(Rhino.RhinoDoc.ActiveDoc.ModelUnitSystem, Rhino.UnitSystem.Centimeters)

    nest = None
    for s in comp.Params.Input[0].Sources:
        o = s.Attributes.GetTopLevel.DocObject
        if o.GetType().FullName.endswith("component_nest1"):
            nest = o
    if nest is None:
        comp.AddRuntimeMessage(Grasshopper.Kernel.GH_RuntimeMessageLevel.Error, "Geo must come from OpenNest")
    else:
        inp = dict((p.Name, p) for p in nest.Params.Input)
        slider = inp["Seed"].Sources[0] if inp["Seed"].Sources else None
        if not isinstance(slider, Grasshopper.Kernel.Special.GH_NumberSlider):
            comp.AddRuntimeMessage(Grasshopper.Kernel.GH_RuntimeMessageLevel.Error, "OpenNest Seed needs a Number Slider")
            slider = None

        def measure():
            """(length, area) of the finished layout in cm / m², None while OpenNest is busy."""
            if not (nest.Message or "").startswith("fit"):
                return None
            box = Rhino.Geometry.BoundingBox.Empty
            for g in nest.Params.Output[1].VolatileData.AllData(True):
                box.Union(g.Boundingbox)
            if not box.IsValid:
                return None
            x0 = min(g.Boundingbox.Min.X for g in inp["Sheets"].VolatileData.AllData(True))
            length = (box.Max.X - x0) * cm
            return length, length * (box.Max.Y - box.Min.Y) * cm / 1e4

        def set_seed(value):
            st["asked"] = value
            def cb(doc):
                v = System.Decimal(value)
                if v > slider.Slider.Maximum:
                    slider.Slider.Maximum = v
                if v < slider.Slider.Minimum:
                    slider.Slider.Minimum = v
                slider.SetSliderValue(v)
                slider.ExpireSolution(False)
            gd.ScheduleSolution(5, Grasshopper.Kernel.GH_Document.GH_ScheduleDelegate(cb))

        was_on = sc.sticky.get(key + "_run", False)
        sc.sticky[key + "_run"] = bool(Run)
        if Run and slider and not was_on:
            st = sc.sticky[key] = {"run": True, "seeds": list(range(From, From + Count)),
                                   "results": [], "t0": time.time(), "busy": False, "asked": None}
        elif not Run and was_on and st and st["run"]:
            st["run"] = False
            if st["results"]:
                set_seed(pick(st["results"], Tol)[0])

        if st and st["run"]:
            seed = st["seeds"][0]
            done = measure()
            if int(slider.CurrentValue) != seed:
                st["busy"] = False
                if st.get("asked") != seed:
                    set_seed(seed)
            elif done is None:
                st["busy"] = True
            elif st["busy"] or not st["results"]:
                # ponytail: no per-seed timeout — if OpenNest never prints "fit" the search waits; Run off stops it
                st["results"].append((seed, done[0], done[1]))
                st["seeds"].pop(0)
                st["busy"] = False
                late = Minutes and time.time() - st["t0"] > Minutes * 60
                if st["seeds"] and not late:
                    set_seed(st["seeds"][0])
                else:
                    st["run"] = False
                    set_seed(pick(st["results"], Tol)[0])

        if st and st["results"]:
            best = pick(st["results"], Tol)
            Seed, L, A = best
            Table = table(st["results"], Tol)
            comp.Message = "%s %d/%d  best %d" % ("seed" if st["run"] else "done", len(st["results"]),
                                                  len(st["results"]) + len(st["seeds"]), best[0])
        else:
            comp.Message = "seed %d…" % st["seeds"][0] if st and st["run"] else "Run = True"


if __name__ == "__main__" and "ghenv" not in globals():
    r = [(1, 1500.0, 30.0), (2, 1439.2, 29.8), (3, 1439.9, 28.0), (4, 1441.0, 20.0)]
    assert pick(r, 1.0)[0] == 3       # 1439.9 within 1 cm of the shortest, smaller area
    assert pick(r, 0.5)[0] == 2       # only the shortest
    assert pick(r, 2.0)[0] == 4
    assert pick([], 1.0) is None
    assert table(r, 1.0)[0].startswith("3 ")
    print("ok")
