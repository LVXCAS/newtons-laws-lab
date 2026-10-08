"""Build N1L tables/graphs from the N2L coasting phase, and CSV versions of the N2L tables."""
import csv
import os
import statistics
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(__file__))
from build_n2l import CART_KG, DOCS, TRIALS, WEIGHT_KG, analyze, linfit  # noqa: E402
from export_gambl import read_runs  # noqa: E402

COLORS = ["#1F6F6F", "#2E75B6", "#C55A11", "#7030A0", "#BF9000"]


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def r(x, n=4):
    return round(x, n)


def coast_stats(res):
    pts = [res["pts"][i] for i in sorted(res["coast"])]
    t, x, v = [p[0] for p in pts], [p[1] for p in pts], [p[2] for p in pts]
    v_slope, _, _ = linfit(t, v)
    x_slope, x_icpt, x_r2 = linfit(t, x)
    return {"pts": pts, "t0": t[0], "t1": t[-1], "v0": v[0], "v1": v[-1], "v_avg": statistics.mean(v),
            "v_sd": statistics.stdev(v), "pct": 100 * (v[-1] - v[0]) / v[0],
            "a": v_slope, "x_slope": x_slope, "x_icpt": x_icpt, "x_r2": x_r2}


def n2l_csvs(rows, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for row in rows:
        data = []
        for i, p in enumerate(row["pts"]):
            phase = "Launch" if i in row["push"] else "Coasting" if i in row["coast"] else ""
            data.append([r(p[0], 2), r(p[1]), r(p[2]), r(p[3]), phase])
        write_csv(os.path.join(out_dir, f"{row['name']} Trial data.csv"),
                  ["Time (s)", "Position (m)", "Velocity (m/s)", "Acceleration (m/s²)", "Phase"], data)
    masses = [CART_KG + row["weights"] * WEIGHT_KG for row in rows]
    accs = [row["a_push"] for row in rows]
    write_csv(os.path.join(out_dir, "N2L Results - Acceleration vs Mass.csv"),
              ["Trial", "Weights added", "Total mass m (kg)", "1/m (1/kg)", "Launch a (m/s²)",
               "F = m·a (N)", "Peak v (m/s)", "Sensor peak a (m/s²)"],
              [[row["name"], row["weights"], r(m, 3), r(1 / m), r(a, 3), r(m * a, 3),
                r(row["vpk"], 3), r(row["sensor_peak_a"], 3)]
               for row, m, a in zip(rows, masses, accs)])
    slope, icpt, r2 = linfit([1 / m for m in masses], accs)
    write_csv(os.path.join(out_dir, "N2L Best-fit line (a vs 1-m).csv"),
              ["Quantity", "Value"],
              [["Slope (= launch force F, N)", r(slope)], ["Intercept (m/s²)", r(icpt)], ["R²", r(r2)],
               ["Correlation a vs m", r(statistics.correlation(accs, masses))]])


def n1l_trial_graph(name, mass, cs, out_png):
    t = [p[0] for p in cs["pts"]]
    fig, (ax_x, ax_v) = plt.subplots(2, 1, figsize=(8, 6.5), sharex=True)
    ax_x.plot(t, [p[1] for p in cs["pts"]], "o", ms=4, color="#1F6F6F", label="Measured position")
    ax_x.plot(t, [cs["x_slope"] * ti + cs["x_icpt"] for ti in t], "--", color="#C00000",
              label=f"Best fit: x = {cs['x_slope']:.3f}t {cs['x_icpt']:+.3f}  (R² = {cs['x_r2']:.4f})")
    ax_x.set_ylabel("Position (m)")
    ax_x.legend(fontsize=8)
    ax_v.plot(t, [p[2] for p in cs["pts"]], "o-", ms=4, color="#1F6F6F")
    ax_v.axhline(cs["v_avg"], ls="--", color="#C00000", label=f"Average v = {cs['v_avg']:.3f} m/s")
    ax_v.set_ylim(0, cs["v0"] * 1.3)
    ax_v.set_ylabel("Velocity (m/s)")
    ax_v.set_xlabel("Time (s)")
    ax_v.legend(fontsize=8)
    for ax in (ax_x, ax_v):
        ax.grid(alpha=0.3)
    fig.suptitle(f"{name.replace('N2L', 'N1L')} — coasting after launch, mass {mass:.3f} kg\n"
                 f"straight x-t line / flat v-t line = constant velocity (net force ≈ 0)",
                 fontweight="bold", fontsize=11)
    fig.tight_layout()
    fig.savefig(out_png, dpi=120)
    plt.close(fig)


def n1l_summary_graphs(rows, stats, out_dir):
    fig, ax = plt.subplots(figsize=(9, 5))
    for row, cs, color in zip(rows, stats, COLORS):
        m = CART_KG + row["weights"] * WEIGHT_KG
        t = [p[0] - cs["t0"] for p in cs["pts"]]
        ax.plot(t, [p[2] for p in cs["pts"]], "o-", ms=3, color=color, label=f"{m:.3f} kg")
    ax.set(xlabel="Time since coasting began (s)", ylabel="Velocity (m/s)", ylim=(0, 0.75),
           title="N1L — every cart keeps a nearly constant velocity once the push stops")
    ax.legend(title="Total mass")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "N1L Results - coasting velocity all trials.png"), dpi=120)
    plt.close(fig)

    masses = [CART_KG + row["weights"] * WEIGHT_KG for row in rows]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(masses, [row["vpk"] for row in rows], "o-", color="#1F6F6F", ms=8)
    ax.set(xlabel="Total mass m (kg)", ylabel="Speed after the same plunger push (m/s)",
           title="N1L inertia — more mass resists the change in motion more")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "N1L Results - inertia (launch speed vs mass).png"), dpi=120)
    plt.close(fig)


def n1l_csvs(rows, stats, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for row, cs in zip(rows, stats):
        write_csv(os.path.join(out_dir, f"{row['name'].replace('N2L', 'N1L')} Coasting data.csv"),
                  ["Time (s)", "Time since coasting began (s)", "Position (m)", "Velocity (m/s)",
                   "Acceleration (m/s²)", "Change in v from start of coast (m/s)"],
                  [[r(p[0], 2), r(p[0] - cs["t0"], 2), r(p[1]), r(p[2]), r(p[3]), r(p[2] - cs["v0"])]
                   for p in cs["pts"]])
    write_csv(os.path.join(out_dir, "N1L Results - Constant velocity while coasting.csv"),
              ["Trial", "Total mass m (kg)", "Coast start (s)", "Coast end (s)", "Coast duration (s)",
               "v at start (m/s)", "v at end (m/s)", "Average v (m/s)", "Std dev of v (m/s)",
               "% change in v", "Coasting a = slope of v-t (m/s²)", "Slope of x-t (m/s)", "R² of x-t line"],
              [[row["name"].replace("N2L", "N1L"), r(CART_KG + row["weights"] * WEIGHT_KG, 3),
                r(cs["t0"], 2), r(cs["t1"], 2), r(cs["t1"] - cs["t0"], 2), r(cs["v0"]), r(cs["v1"]),
                r(cs["v_avg"]), r(cs["v_sd"]), r(cs["pct"], 1), r(cs["a"]), r(cs["x_slope"]), r(cs["x_r2"], 5)]
               for row, cs in zip(rows, stats)])
    inertia = []
    for row in rows:
        m = CART_KG + row["weights"] * WEIGHT_KG
        inertia.append([row["name"].replace("N2L", "N1L"), row["weights"], r(m, 3), r(row["vpk"]),
                        r(row["a_push"], 3), r(m * row["vpk"])])
    write_csv(os.path.join(out_dir, "N1L Results - Inertia (same push, different mass).csv"),
              ["Trial", "Weights added", "Total mass m (kg)", "Speed after push (m/s)",
               "Launch a (m/s²)", "Momentum m·v (kg·m/s)"], inertia)


def main(n2l_dir, n1l_dir):
    runs = read_runs(os.path.join(DOCS, "N2L_5.gambl"))
    rows = [{"name": name, "weights": w, **analyze(runs[num - 1])} for name, num, w in TRIALS]
    stats = [coast_stats(row) for row in rows]
    n2l_csvs(rows, os.path.join(n2l_dir, "CSV tables"))
    graphs = os.path.join(n1l_dir, "Graphs")
    os.makedirs(graphs, exist_ok=True)
    for row, cs in zip(rows, stats):
        m = CART_KG + row["weights"] * WEIGHT_KG
        name = row["name"].replace("N2L", "N1L")
        n1l_trial_graph(row["name"], m, cs, os.path.join(graphs, f"{name} - coasting position and velocity.png"))
        print(f"{name}: m={m:.3f} coast {cs['t0']:.2f}-{cs['t1']:.2f}s v {cs['v0']:.3f}->{cs['v1']:.3f} "
              f"avg {cs['v_avg']:.3f} sd {cs['v_sd']:.4f} ({cs['pct']:.1f}%) a {cs['a']:.4f} "
              f"x-t slope {cs['x_slope']:.4f} R2 {cs['x_r2']:.5f} p=mv {m * row['vpk']:.3f}")
    n1l_summary_graphs(rows, stats, graphs)
    n1l_csvs(rows, stats, os.path.join(n1l_dir, "CSV tables"))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
