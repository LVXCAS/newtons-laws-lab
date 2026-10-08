"""Build ANGLED (incline) tables (CSV) and graphs (PNG): constant acceleration on a ramp."""
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(__file__))
from build_n1l import write_csv  # noqa: E402
from build_n2l import DOCS, linfit  # noqa: E402
from export_gambl import present, read_runs  # noqa: E402

G = 9.8
RUNS = [(33, "Rolls up and down the ramp, bouncing off the bottom stop"),
        (34, "Plunger launch up the ramp, stops, rolls back down")]
BLANK = [(35, "No motion recorded")]
FREE_TOL = 0.25     # m/s²; free-rolling samples sit within this of the ramp acceleration
MIN_SEG = 6         # samples; shorter stretches are bounce/launch transients
STOP_V = 0.03       # m/s; samples this slow are dropped when splitting up/down at the turnaround


def free_segments(pts):
    """Contiguous stretches where the cart rolls freely (acceleration ≈ steady negative value)."""
    accs = sorted(p[3] for p in pts if p[3] < -0.2)
    a_ramp = accs[len(accs) // 2]
    segs, cur = [], []
    for i, p in enumerate(pts):
        if abs(p[3] - a_ramp) < FREE_TOL:
            cur.append(i)
        else:
            if len(cur) >= MIN_SEG:
                segs.append(cur)
            cur = []
    if len(cur) >= MIN_SEG:
        segs.append(cur)
    return segs


def split_up_down(pts, seg):
    up = [i for i in seg if pts[i][2] > STOP_V]
    down = [i for i in seg if pts[i][2] < -STOP_V]
    return [(name, idx) for name, idx in (("Up the ramp", up), ("Down the ramp", down)) if len(idx) >= 4]


def analyze(run):
    c = run["cols"]
    pts = present(c["Time (s)"], c["Position G (m)"], c["Velocity G (m/s)"], c["Acceleration G (m/s²)"])
    parts = []
    for seg in free_segments(pts):
        for direction, idx in split_up_down(pts, seg):
            t = [pts[i][0] for i in idx]
            v = [pts[i][2] for i in idx]
            a, b, r2 = linfit(t, v)
            parts.append({"dir": direction, "idx": idx, "t0": t[0], "t1": t[-1], "a": a, "b": b, "r2": r2,
                          "v0": v[0], "v1": v[-1]})
    return pts, parts


def plot_run(num, kind, pts, parts, out_png):
    t = [p[0] for p in pts]
    fig, (ax_x, ax_v) = plt.subplots(2, 1, figsize=(8, 6.5), sharex=True)
    ax_x.plot(t, [p[1] for p in pts], color="#1F6F6F", lw=2)
    ax_x.set_ylabel("Position along ramp (m)")
    ax_v.plot(t, [p[2] for p in pts], color="#1F6F6F", lw=2, label="Measured velocity")
    seen = set()
    for part in parts:
        color = "#C00000" if part["dir"] == "Up the ramp" else "#2E75B6"
        ts = [part["t0"], part["t1"]]
        label = None if part["dir"] in seen else f"{part['dir']}: best-fit line (slope = a)"
        seen.add(part["dir"])
        ax_v.plot(ts, [part["a"] * x + part["b"] for x in ts], "--", color=color, lw=2, label=label)
        ax_v.annotate(f"a = {part['a']:.3f}", (part["t1"], part["a"] * part["t1"] + part["b"]),
                      fontsize=7, color=color, xytext=(4, 0), textcoords="offset points")
    ax_v.set_ylabel("Velocity (m/s)  (+ = up the ramp)")
    ax_v.set_xlabel("Time (s)")
    ax_v.legend(fontsize=8)
    for ax in (ax_x, ax_v):
        ax.axhline(0, color="black", lw=0.6)
        ax.grid(alpha=0.3)
    fig.suptitle(f"ANGLED Run {num} — {kind}\nStraight v-t lines = constant acceleration from gravity along the ramp",
                 fontweight="bold", fontsize=10)
    fig.tight_layout()
    fig.savefig(out_png, dpi=120)
    plt.close(fig)


def r(x, n=4):
    return round(x, n)


def main(out_dir):
    csv_dir, graph_dir = os.path.join(out_dir, "CSV tables"), os.path.join(out_dir, "Graphs")
    os.makedirs(csv_dir, exist_ok=True)
    os.makedirs(graph_dir, exist_ok=True)
    runs = read_runs(os.path.join(DOCS, "ANGLED.gambl"))
    table, ups, downs = [], [], []
    for num, kind in RUNS:
        pts, parts = analyze(runs[num - 1])
        plot_run(num, kind, pts, parts, os.path.join(graph_dir, f"ANGLED Run {num} - position and velocity.png"))
        phase = {}
        for k, part in enumerate(parts, start=1):
            for i in part["idx"]:
                phase[i] = f"Free roll {k} ({part['dir'].lower()})"
            table.append([num, k, part["dir"], r(part["t0"], 2), r(part["t1"], 2), r(part["v0"]), r(part["v1"]),
                          r(part["a"]), r(part["r2"], 5)])
            (ups if part["dir"] == "Up the ramp" else downs).append(part["a"])
            print(num, k, part["dir"], f"{part['t0']:.2f}-{part['t1']:.2f}", f"a={part['a']:.4f}", f"R2={part['r2']:.5f}")
        write_csv(os.path.join(csv_dir, f"ANGLED Run {num} data.csv"),
                  ["Time (s)", "Position (m)", "Velocity (m/s)", "Acceleration (m/s²)", "Phase"],
                  [[r(p[0], 2), r(p[1]), r(p[2]), r(p[3]), phase.get(i, "")] for i, p in enumerate(pts)])
    write_csv(os.path.join(csv_dir, "ANGLED Results - Acceleration on the ramp.csv"),
              ["Run", "Segment", "Direction", "Start (s)", "End (s)", "v at start (m/s)", "v at end (m/s)",
               "Acceleration = slope of v-t (m/s²)", "R² of v-t line"], table)

    a_up, a_down = sum(ups) / len(ups), sum(downs) / len(downs)
    # Up: a = -(g sinθ + f);  down: a = -(g sinθ - f), with f = friction deceleration
    g_sin = -(a_up + a_down) / 2
    friction = -(a_up - a_down) / 2
    theta = math.degrees(math.asin(g_sin / G))
    summary = [
        ["Average acceleration rolling UP the ramp (m/s²)", r(a_up), f"{len(ups)} segments"],
        ["Average acceleration rolling DOWN the ramp (m/s²)", r(a_down), f"{len(downs)} segments"],
        ["Gravity's pull along the ramp, g·sinθ (m/s²)", r(g_sin), "= -(a_up + a_down)/2"],
        ["Friction/drag deceleration (m/s²)", r(friction), "= -(a_up - a_down)/2"],
        ["Ramp angle θ from the data (degrees)", r(theta, 2), "= asin(g·sinθ / 9.8)"],
        ["Note", "", "Mass cancels: a = g·sinθ for any mass, so this works without knowing the cart's mass"],
    ]
    write_csv(os.path.join(csv_dir, "ANGLED Results - Ramp angle and friction.csv"),
              ["Quantity", "Value", "How it's found"], summary)
    write_csv(os.path.join(csv_dir, "ANGLED Notes - skipped runs.csv"), ["Run", "Note"],
              [[n, why] for n, why in BLANK])
    print(f"a_up {a_up:.4f} a_down {a_down:.4f} g sin {g_sin:.4f} friction {friction:.4f} theta {theta:.2f} deg")


if __name__ == "__main__":
    main(sys.argv[1])
