# -*- coding: utf-8 -*-
"""SeedSearch — GhPython component for autonest_v2.gh and autonest_v3.gh.

Tries OpenNest2 seeds one after another and keeps the layout that takes the
least material along X; among the shortest (within Tol) — the smallest
bounding box area. OpenNest2 runs its generations over many solutions, so
Galapagos can't score it; this component waits for each result ("fit …").
A panel that doesn't fit OpenNest puts on an extra copy of the sheet (IDS ≥
number of sheets): such a layout is missing panels and never wins over one
with all of them; its length counts only the panels on the real sheet.

Inputs:
    Geo     : Geo output of OpenNest (v2) / All Geo of OpenNest2 (v3), Tree access (only
              to be solved when it changes; the layout is read from the nest itself)
    Run     : Boolean Toggle — True starts a new search, False stops it
    From    : first seed (default 1)
    Count   : how many seeds (default 50)
    Minutes : time limit, 0 — none
    Tol     : cm — lengths within Tol count as equally short (default 1)
Outputs:
    Seed    : best seed (set on the Seed slider / OpenNest2's Seed option at the end)
    L       : its length along X, cm
    A       : its bounding box area, m²
    Table   : "seed  L cm  A m²  [missing n]" per tried seed, best first
"""


SETTLE = 6          # s after a new seed: a finished layout is taken as its own even if "busy" was never seen (OpenNest2 restarts between two looks); ponytail: a restart later than this takes the old layout
NESTS = ("component_nest1", "component2_nest")      # OpenNest (v2), OpenNest2 (v3)


def finished(message):
    """OpenNest ends with "fit …", OpenNest2 with "<n> gens → <k> sheet(s)"."""
    message = message or ""
    return message.startswith("fit") or "sheet(s)" in message


def pick(results, tol):
    """(seed, length, area, missing) list → best one: fewest missing panels, then shortest within tol, then least area."""
    if not results:
        return None
    least = min(r[3] for r in results)
    full = [r for r in results if r[3] == least]
    short = min(r[1] for r in full)
    return min((r for r in full if r[1] <= short + tol), key=lambda r: (r[2], r[1]))


def table(results, tol):
    best = pick(results, tol)
    rows = sorted(results, key=lambda r: (r[3], r[1], r[2]))
    rows.remove(best)
    return ["%d  %.1f cm  %.3f m2" % r[:3] + ("  missing %d" % r[3] if r[3] else "") for r in [best] + rows]


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
    Count = max(1, int(Count or 50))
    Minutes = float(Minutes or 0)
    Tol = 1.0 if Tol is None else float(Tol)
    cm = Rhino.RhinoMath.UnitScale(Rhino.RhinoDoc.ActiveDoc.ModelUnitSystem, Rhino.UnitSystem.Centimeters)

    nest = next((o for o in (s.Attributes.GetTopLevel.DocObject for s in comp.Params.Input[0].Sources)
                 if o.GetType().FullName.endswith(NESTS)), None)
    inp = dict((p.Name, p) for p in nest.Params.Input) if nest else {}
    v3 = bool(nest) and nest.GetType().FullName.endswith("component2_nest")
    opt = None
    if v3:      # OpenNest2: sheets on the Sheets component; Seed an option of the nest itself
        owner = lambda p: p.Sources[0].Attributes.GetTopLevel.DocObject if p.Sources else None
        shs = owner(inp["Sheets"])
        sheet_in = shs.Params.Input[0] if shs else None
        if not inp["Options"].Sources:      # own options (the panel on the component); a wired Options overrides them
            opt = next((o for o in nest.Options if o.Key == "seed"), None)
        else:
            opts = owner(inp["Options"])
            seed_in = dict((p.Name, p) for p in opts.Params.Input).get("Seed") if opts else None
    else:
        seed_in, sheet_in = inp.get("Seed"), inp.get("Sheets")
    slider = None if opt else (seed_in.Sources[0] if seed_in is not None and seed_in.Sources else None)
    if not opt and not isinstance(slider, Grasshopper.Kernel.Special.GH_NumberSlider):
        comp.AddRuntimeMessage(Grasshopper.Kernel.GH_RuntimeMessageLevel.Error,
                               "Geo must come from OpenNest / OpenNest2 — its Seed from a Number Slider (or OpenNest2's own Seed option)")
    else:
        seed_now = lambda: int(opt.Value if opt else slider.CurrentValue)

        def measure():
            """(length, area, missing panels) of the finished layout in cm / m², None while OpenNest is busy."""
            if not finished(nest.Message):
                return None
            # parts as placed (v2 Geo, v3 All Geo — Borders are grown by the spacing) and their sheet numbers
            geo, sheet_of = nest.Params.Output[2 if v3 else 1].VolatileData, nest.Params.Output[4].VolatileData
            sheets = list(sheet_in.VolatileData.AllData(True))
            box = Rhino.Geometry.BoundingBox.Empty
            placed = 0
            for i in range(min(geo.PathCount, sheet_of.PathCount)):
                if geo.Branches[i].Count and sheet_of.Branches[i].Count and 0 <= sheet_of.Branches[i][0].Value < len(sheets):
                    placed += 1
                    for g in geo.Branches[i]:
                        box.Union(g.Boundingbox)
            total = geo.PathCount if v3 else inp["Geo"].VolatileDataCount
            if not box.IsValid:
                return float("inf"), float("inf"), total      # nothing placed — the worst layout, not "busy"
            x0 = min(g.Boundingbox.Min.X for g in sheets)
            length = (box.Max.X - x0) * cm
            # one curve per part (the Cut list grafted)
            return length, length * (box.Max.Y - box.Min.Y) * cm / 1e4, total - placed

        def set_seed(value):
            """Seed on the slider at the next solution; the result on screen is not its own until OpenNest restarts."""
            st["fresh"], st["seen"], st["t_set"] = False, False, time.time()
            def cb(doc):
                if opt:         # same call the option field makes when typed into
                    opt.Value = float(value)
                    flags = System.Reflection.BindingFlags
                    nest.GetType().BaseType.GetMethod("OnOptionChanged", flags.NonPublic | flags.Public | flags.Instance).Invoke(nest, [opt])
                    nest.ExpireSolution(False)      # the option alone doesn't restart it ("live — watching")
                    return
                v = System.Decimal(value)
                slider.Slider.Maximum = max(slider.Slider.Maximum, v)
                slider.Slider.Minimum = min(slider.Slider.Minimum, v)
                slider.SetSliderValue(v)
                slider.ExpireSolution(False)
            gd.ScheduleSolution(5, Grasshopper.Kernel.GH_Document.GH_ScheduleDelegate(cb))

        def stop():
            st["run"] = False
            if st["results"] and pick(st["results"], Tol)[0] != seed_now():      # no restart if the best is on screen
                set_seed(pick(st["results"], Tol)[0])

        if Run and not st["on"]:
            st.update(run=True, seeds=list(range(From, From + Count)), results=[], t0=time.time())
            if seed_now() == From:
                st["fresh"] = True
            else:
                set_seed(From)
        elif not Run and st["on"] and st["run"]:
            stop()
        st["on"] = bool(Run)

        # ponytail: no per-seed timeout — if OpenNest never prints "fit" the search waits; Run off stops it
        if st["run"] and seed_now() == st["seeds"][0]:
            done = measure()
            if done is None:
                st["fresh"], st["seen"] = True, False
            elif not (st["fresh"] or time.time() - st.get("t_set", 0) > SETTLE):
                pass
            elif not st.get("seen"):
                st["seen"] = True       # finished — taken after a second look (message and outputs are not updated at one moment)
            else:
                st["results"].append((st["seeds"].pop(0),) + done)
                st["seen"] = False
                if st["seeds"] and not (Minutes and time.time() - st["t0"] > Minutes * 60):
                    set_seed(st["seeds"][0])
                else:
                    stop()

        if st["run"]:       # OpenNest2 expires its outputs only when the layout changed: look again while waiting
            gd.ScheduleSolution(500, Grasshopper.Kernel.GH_Document.GH_ScheduleDelegate(lambda doc: comp.ExpireSolution(False)))

        n = len(st["results"])
        if n:
            Seed, L, A, missing = pick(st["results"], Tol)
            Table = table(st["results"], Tol)
            if missing:
                comp.AddRuntimeMessage(Grasshopper.Kernel.GH_RuntimeMessageLevel.Warning,
                                       "every seed so far leaves %d panel(s) off the sheet" % missing)
        comp.Message = ("%s %d/%d" % ("seed" if st["run"] else "done", n, n + len(st["seeds"])) if st["seeds"] or n
                        else "Run = True") + ("  best %d" % Seed if n else "")


if __name__ == "__main__" and "ghenv" not in globals():
    r = [(1, 1500.0, 30.0, 0), (2, 1439.2, 29.8, 0), (3, 1439.9, 28.0, 0), (4, 1441.0, 20.0, 0), (5, 900.0, 15.0, 1)]
    assert pick(r, 1.0)[0] == 3       # 1439.9 within 1 cm of the shortest, smaller area
    assert pick(r, 0.5)[0] == 2       # only the shortest
    assert pick(r, 2.0)[0] == 4
    assert pick([], 1.0) is None
    assert table(r, 1.0)[0].startswith("3 ")
    assert table(r, 1.0)[-1] == "5  900.0 cm  15.000 m2  missing 1"   # shorter, but a panel short — last
    assert pick([(5, 900.0, 15.0, 2), (6, 950.0, 15.0, 1)], 1.0)[0] == 6
    assert finished("fit 12.3") and finished("100 gens   \u2192   1 sheet(s)") and not finished("gen 5 / 100") and not finished(None)
    print("ok")
