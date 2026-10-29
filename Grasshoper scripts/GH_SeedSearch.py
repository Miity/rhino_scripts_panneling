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
    st = sc.sticky.setdefault("SeedSearch.%s" % comp.InstanceGuid, {"on": False, "run": False, "seeds": [], "results": []})
    From = 1 if From is None else int(From)
    Count = int(Count or 50)
    Minutes = float(Minutes or 0)
    Tol = 1.0 if Tol is None else float(Tol)
    cm = Rhino.RhinoMath.UnitScale(Rhino.RhinoDoc.ActiveDoc.ModelUnitSystem, Rhino.UnitSystem.Centimeters)

    nest = next((o for o in (s.Attributes.GetTopLevel.DocObject for s in comp.Params.Input[0].Sources)
                 if o.GetType().FullName.endswith("component_nest1")), None)
    inp = dict((p.Name, p) for p in nest.Params.Input) if nest else {}
    slider = inp["Seed"].Sources[0] if nest and inp["Seed"].Sources else None
    if not isinstance(slider, Grasshopper.Kernel.Special.GH_NumberSlider):
        comp.AddRuntimeMessage(Grasshopper.Kernel.GH_RuntimeMessageLevel.Error,
                               "Geo must come from OpenNest, its Seed from a Number Slider")
    else:
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
            """Seed on the slider at the next solution; the result on screen is not its own until OpenNest restarts."""
            st["fresh"] = False
            def cb(doc):
                v = System.Decimal(value)
                slider.Slider.Maximum = max(slider.Slider.Maximum, v)
                slider.Slider.Minimum = min(slider.Slider.Minimum, v)
                slider.SetSliderValue(v)
                slider.ExpireSolution(False)
            gd.ScheduleSolution(5, Grasshopper.Kernel.GH_Document.GH_ScheduleDelegate(cb))

        def stop():
            st["run"] = False
            if st["results"]:
                set_seed(pick(st["results"], Tol)[0])

        if Run and not st["on"]:
            st.update(run=True, seeds=list(range(From, From + Count)), results=[], t0=time.time())
            if int(slider.CurrentValue) == From:
                st["fresh"] = True
            else:
                set_seed(From)
        elif not Run and st["on"] and st["run"]:
            stop()
        st["on"] = bool(Run)

        # ponytail: no per-seed timeout — if OpenNest never prints "fit" the search waits; Run off stops it
        if st["run"] and int(slider.CurrentValue) == st["seeds"][0]:
            done = measure()
            if done is None:
                st["fresh"] = True
            elif st["fresh"]:
                st["results"].append((st["seeds"].pop(0),) + done)
                if st["seeds"] and not (Minutes and time.time() - st["t0"] > Minutes * 60):
                    set_seed(st["seeds"][0])
                else:
                    stop()

        n = len(st["results"])
        if n:
            Seed, L, A = pick(st["results"], Tol)
            Table = table(st["results"], Tol)
        comp.Message = ("%s %d/%d" % ("seed" if st["run"] else "done", n, n + len(st["seeds"])) if st["seeds"] or n
                        else "Run = True") + ("  best %d" % Seed if n else "")


if __name__ == "__main__" and "ghenv" not in globals():
    r = [(1, 1500.0, 30.0), (2, 1439.2, 29.8), (3, 1439.9, 28.0), (4, 1441.0, 20.0)]
    assert pick(r, 1.0)[0] == 3       # 1439.9 within 1 cm of the shortest, smaller area
    assert pick(r, 0.5)[0] == 2       # only the shortest
    assert pick(r, 2.0)[0] == 4
    assert pick([], 1.0) is None
    assert table(r, 1.0)[0].startswith("3 ")
    print("ok")
