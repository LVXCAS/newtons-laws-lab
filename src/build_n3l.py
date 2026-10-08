"""Build N3L tables (CSV) and graphs (PNG) from the N3L collision runs."""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(__file__))
from build_n1l import write_csv  # noqa: E402
from build_n2l import CART_KG, DOCS, WEIGHT_KG  # noqa: E402
from export_gambl import present, read_runs  # noqa: E402

CONTACT_A = 0.15   # m/s²; a cart counts as "being pushed" while |a| exceeds this
PAD = 2            # samples taken outside the contact window for before/after velocities
AVG_N = 3          # samples averaged for the before/after velocity
# (run, source file, Y weights, G weights, kind). Weights inferred from the velocity-change pattern.
RUNS = [
    (3, "N3L", 0, 3, "Car 1 hits Car 2 (Car 2 at rest)"),
    (5, "N3L", 0, 3, "Car 1 hits Car 2 (Car 2 at rest)"),
    (6, "N3L", 0, 3, "Car 1 hits Car 2 (Car 2 at rest)"),
    (8, "N3L", 0, 3, "Car 1 hits Car 2 (Car 2 at rest)"),
    (9, "N3L_2", 0, 1, "Car 1 hits Car 2 (Car 2 at rest)"),
    (10, "N3L_3", 0, 0, "Car 1 hits Car 2 (Car 2 at rest)"),
    (12, "N3L_4", 4, 0, "Car 1 hits Car 2 (Car 2 at rest)"),
    (4, "N3L", 0, 0, "Push apart from rest (plunger)"),
    (16, "N3L_6", 0, 0, "Push apart from rest (plunger)"),
]
ROUGH = [(15, "N3L_6", "Head-on; recording started mid-collision, so 'before' velocities are missing")]
NO_COLLISION = [(1, "N3L"), (2, "N3L"), (7, "N3L"), (11, "N3L_4"), (13, "N3L_5"), (14, "N3L_6")]


def mass(n):
    return CART_KG + n * WEIGHT_KG


def contact_window(pts):
    k = max(range(len(pts)), key=lambda i: min(abs(pts[i][3]), abs(pts[i][4])))
    lo = hi = k
    while lo > 0 and max(abs(pts[lo - 1][3]), abs(pts[lo - 1][4])) > CONTACT_A:
        lo -= 1
    while hi < len(pts) - 1 and max(abs(pts[hi + 1][3]), abs(pts[hi + 1][4])) > CONTACT_A:
        hi += 1
    return k, lo, hi


def avg(vals):
    return sum(vals) / len(vals)


def analyze(run, ny, ng):
    c = run["cols"]
    pts = present(c["Time (s)"], c["Velocity Y (m/s)"], c["Velocity G (m/s)"],
                  c["Acceleration Y (m/s²)"], c["Acceleration G (m/s²)"])
    k, lo, hi = contact_window(pts)
    b, a = max(lo - PAD, 0), min(hi + PAD, len(pts) - 1)
    before = pts[max(b - AVG_N + 1, 0):b + 1]
    after = pts[a:a + AVG_N]
    my, mg = mass(ny), mass(ng)
    # Each cart's sensor measures along its own direction. When both raw accelerations share a sign
    # during contact, the carts were facing each other, so Y is flipped into G's frame.
    flip = -1 if pts[k][3] * pts[k][4] > 0 else 1
    dvy = flip * (avg([p[1] for p in after]) - avg([p[1] for p in before]))
    dvg = avg([p[2] for p in after]) - avg([p[2] for p in before])
    fy = [flip * my * p[3] for p in pts]
    fg = [mg * p[4] for p in pts]
    peak_fy = max((fy[i] for i in range(lo, hi + 1)), key=abs)
    peak_fg = max((fg[i] for i in range(lo, hi + 1)), key=abs)
    return {"pts": pts, "lo": lo, "hi": hi, "flip": flip, "my": my, "mg": mg,
            "vy0": flip * avg([p[1] for p in before]), "vy1": flip * avg([p[1] for p in after]),
            "vg0": avg([p[2] for p in before]), "vg1": avg([p[2] for p in after]),
            "dvy": dvy, "dvg": dvg, "jy": my * dvy, "jg": mg * dvg, "fy": fy, "fg": fg,
            "peak_fy": peak_fy, "peak_fg": peak_fg,
            "t_contact": (pts[lo][0], pts[hi][0])}


def pct_diff(x, y):
    return 100 * abs(abs(x) - abs(y)) / ((abs(x) + abs(y)) / 2)


def plot_run(num, src, kind, res, out_png):
    pts = res["pts"]
    t = [p[0] for p in pts]
    fig, (ax_v, ax_f) = plt.subplots(2, 1, figsize=(8, 6.5), sharex=True)
    ax_v.plot(t, [p[2] for p in pts], color="#1F6F6F", lw=2, label=f"Car 1 ({res['mg']:.3f} kg)")
    ax_v.plot(t, [res["flip"] * p[1] for p in pts], color="#C9A400", lw=2, label=f"Car 2 ({res['my']:.3f} kg)")
    ax_v.set_ylabel("Velocity (m/s)")
    ax_f.plot(t, res["fg"], color="#1F6F6F", lw=2, label="Force on Car 1  (m·a)")
    ax_f.plot(t, res["fy"], color="#C9A400", lw=2, label="Force on Car 2  (m·a)")
    ax_f.set_ylabel("Force (N)")
    ax_f.set_xlabel("Time (s)")
    for ax in (ax_v, ax_f):
        ax.axvspan(*res["t_contact"], color="#BDD7EE", alpha=0.5, label="Contact")
        ax.axhline(0, color="black", lw=0.6)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8, loc="best")
    fig.suptitle(f"N3L Run {num} ({src}) — {kind}\nForces on the two carts are mirror images: "
                 f"equal size, opposite direction, same contact time", fontweight="bold", fontsize=10)
    fig.tight_layout()
    fig.savefig(out_png, dpi=120)
    plt.close(fig)


def plot_summary(results, out_png):
    labels = [f"Run {num}" for num, *_ in results]
    jy = [abs(res["jy"]) for *_, res in results]
    jg = [abs(res["jg"]) for *_, res in results]
    xs = range(len(labels))
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.bar([x - 0.2 for x in xs], jg, 0.4, color="#1F6F6F", label="|Impulse on Car 1| = m₁·|Δv₁|")
    ax.bar([x + 0.2 for x in xs], jy, 0.4, color="#C9A400", label="|Impulse on Car 2| = m₂·|Δv₂|")
    ax.set_xticks(list(xs), labels)
    ax.set_ylabel("Impulse (N·s)")
    ax.set_title("N3L — each pair of bars matches: the carts push on each other equally (and oppositely)")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_png, dpi=120)
    plt.close(fig)


def r(x, n=4):
    return round(x, n)


def main(out_dir):
    csv_dir, graph_dir = os.path.join(out_dir, "CSV tables"), os.path.join(out_dir, "Graphs")
    os.makedirs(csv_dir, exist_ok=True)
    os.makedirs(graph_dir, exist_ok=True)
    runs = read_runs(os.path.join(DOCS, "N3L_6.gambl"))
    results = []
    for num, src, ny, ng, kind in RUNS:
        res = analyze(runs[num - 1], ny, ng)
        results.append((num, src, kind, ny, ng, res))
        plot_run(num, src, kind, res, os.path.join(graph_dir, f"N3L Run {num:02d} ({src}) - velocity and force.png"))
        rows = []
        for i, p in enumerate(res["pts"]):
            rows.append([r(p[0], 2), r(p[2]), r(res["flip"] * p[1]), r(p[4]), r(res["flip"] * p[3]),
                         r(res["fg"][i]), r(res["fy"][i]), "Contact" if res["lo"] <= i <= res["hi"] else ""])
        write_csv(os.path.join(csv_dir, f"N3L Run {num:02d} ({src}) data.csv"),
                  ["Time (s)", "Velocity Car 1 (m/s)", "Velocity Car 2 (m/s)", "Acceleration Car 1 (m/s²)",
                   "Acceleration Car 2 (m/s²)", "Force on Car 1 = m₁·a₁ (N)", "Force on Car 2 = m₂·a₂ (N)", "Phase"], rows)
        print(f"Run {num:2d}: dvY {res['dvy']:+.3f} dvG {res['dvg']:+.3f} JY {res['jy']:+.4f} JG {res['jg']:+.4f} "
              f"diff {pct_diff(res['jy'], res['jg']):.1f}%  peakF Y {res['peak_fy']:+.3f} G {res['peak_fg']:+.3f} "
              f"diff {pct_diff(res['peak_fy'], res['peak_fg']):.1f}%  contact {res['t_contact']}")

    write_csv(os.path.join(csv_dir, "N3L Results - Equal and opposite impulses.csv"),
              ["Run", "File", "Type", "Car 1 weights", "Car 2 weights", "m₁ (kg)", "m₂ (kg)",
               "v₁ before (m/s)", "v₁ after (m/s)", "v₂ before (m/s)", "v₂ after (m/s)",
               "Δv₁ (m/s)", "Δv₂ (m/s)", "Impulse on Car 1 = m₁·Δv₁ (N·s)", "Impulse on Car 2 = m₂·Δv₂ (N·s)",
               "Sum of impulses (≈0) (N·s)", "% difference in size", "Contact start (s)", "Contact end (s)"],
              [[num, src, kind, ng, ny, r(res["mg"], 3), r(res["my"], 3), r(res["vg0"]), r(res["vg1"]),
                r(res["vy0"]), r(res["vy1"]), r(res["dvg"]), r(res["dvy"]), r(res["jg"]), r(res["jy"]),
                r(res["jy"] + res["jg"]), r(pct_diff(res["jy"], res["jg"]), 1),
                r(res["t_contact"][0], 2), r(res["t_contact"][1], 2)]
               for num, src, kind, ny, ng, res in results])
    write_csv(os.path.join(csv_dir, "N3L Results - Peak contact forces.csv"),
              ["Run", "m₁ (kg)", "m₂ (kg)", "Peak force on Car 1 (N)", "Peak force on Car 2 (N)",
               "Opposite directions?", "% difference in size"],
              [[num, r(res["mg"], 3), r(res["my"], 3), r(res["peak_fg"], 3), r(res["peak_fy"], 3),
                "Yes" if res["peak_fy"] * res["peak_fg"] < 0 else "No",
                r(pct_diff(res["peak_fy"], res["peak_fg"]), 1)]
               for num, src, kind, ny, ng, res in results])
    notes = [["Masses", "Cart = 0.292 kg, each weight = 0.142 kg. Weights per cart were not recorded; they were "
              "inferred as the simplest setup that matches each run's velocity changes, so confirm them."],
             ["Direction", "Each car's sensor measures along its own direction. Car 2's values are flipped into "
              "Car 1's direction when the cars faced each other, so + means the same way for both cars."],
             ["Car labels", "Car 1 = green/blue trace (sensor 'G'), Car 2 = yellow trace (sensor 'Y')."],
             ["Δv", f"Average of {AVG_N} samples just after contact minus {AVG_N} samples just before."]]
    notes += [[f"Run {n} ({s})", why] for n, s, why in ROUGH]
    notes += [[f"Run {n} ({s})", "No collision recorded (carts did not interact)"] for n, s in NO_COLLISION]
    write_csv(os.path.join(csv_dir, "N3L Notes - masses, directions, skipped runs.csv"), ["Item", "Note"], notes)
    plot_summary(results, os.path.join(graph_dir, "N3L Results - impulse on Y vs impulse on G.png"))


if __name__ == "__main__":
    main(sys.argv[1])
