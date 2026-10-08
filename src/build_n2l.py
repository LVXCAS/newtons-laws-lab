"""Build N2L/N1L lab workbooks (one per trial + a results summary) from the .gambl exports."""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from openpyxl import Workbook
from openpyxl.chart import Reference, ScatterChart, Series
from openpyxl.chart.trendline import Trendline
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Font, PatternFill

sys.path.insert(0, os.path.dirname(__file__))
from export_gambl import present, read_runs  # noqa: E402

DATA_DIR = os.environ.get("GAMBL_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data"))
DOCS = DATA_DIR
CART_KG = 0.292
WEIGHT_KG = 0.142
# (file, run number in the session, weights added) — best clean launch in each file.
TRIALS = [("N2L_1", 19, 0), ("N2L_2", 24, 1), ("N2L_3", 27, 2), ("N2L_4", 28, 3), ("N2L_5", 32, 4)]
PUSH_LO, PUSH_HI = 0.10, 0.90   # push window = velocity between 10% and 90% of peak
COAST_DELAY_S = 0.10            # skip the end of the launch before measuring coasting
COAST_FLOOR = 0.80              # coasting ends when v drops below 80% of peak
HEADER_FILL = PatternFill("solid", fgColor="1F4E79")
HEADER_FONT = Font(bold=True, color="FFFFFF")
PUSH_FILL = PatternFill("solid", fgColor="FDE9D9")
COAST_FILL = PatternFill("solid", fgColor="E2EFDA")
TITLE_FONT = Font(bold=True, size=14)
BOLD = Font(bold=True)


def linfit(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    intercept = my - slope * mx
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    r2 = 1 - ss_res / ss_tot if ss_tot else 1.0
    return slope, intercept, r2


def analyze(run):
    c = run["cols"]
    pts = present(c["Time (s)"], c["Position G (m)"], c["Velocity G (m/s)"], c["Acceleration G (m/s²)"])
    ipk = max(range(len(pts)), key=lambda i: pts[i][2])
    vpk = pts[ipk][2]
    push = [i for i in range(ipk + 1) if PUSH_LO * vpk <= pts[i][2] <= PUSH_HI * vpk]
    # keep only the contiguous launch ramp leading into the peak
    while len(push) > 1 and push[1] - push[0] > 1:
        push.pop(0)
    t_coast0 = pts[ipk][0] + COAST_DELAY_S
    coast = []
    for i in range(ipk, len(pts)):
        if pts[i][2] < COAST_FLOOR * vpk:
            break
        if pts[i][0] >= t_coast0:
            coast.append(i)
    a_push, _, r2_push = linfit([pts[i][0] for i in push], [pts[i][2] for i in push])
    a_coast, _, _ = linfit([pts[i][0] for i in coast], [pts[i][2] for i in coast])
    v_coast = sum(pts[i][2] for i in coast) / len(coast)
    return {"pts": pts, "push": set(push), "coast": set(coast), "vpk": vpk,
            "a_push": a_push, "r2_push": r2_push, "a_coast": a_coast, "v_coast": v_coast,
            "push_t": (pts[push[0]][0], pts[push[-1]][0]),
            "coast_t": (pts[coast[0]][0], pts[coast[-1]][0]),
            "sensor_peak_a": max(pts[i][3] for i in range(ipk + 1))}


def header_row(ws, row, labels):
    for col, label in enumerate(labels, start=1):
        cell = ws.cell(row=row, column=col, value=label)
        cell.fill, cell.font = HEADER_FILL, HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def plot_trial(name, mass, res, out_png):
    pts = res["pts"]
    t = [p[0] for p in pts]
    fig, (ax_v, ax_a) = plt.subplots(2, 1, figsize=(8, 6.5), sharex=True)
    ax_v.plot(t, [p[2] for p in pts], color="#1F6F6F", lw=2)
    ax_a.plot(t, [p[3] for p in pts], color="#1F6F6F", lw=2)
    for ax in (ax_v, ax_a):
        ax.axvspan(*res["push_t"], color="#F4B183", alpha=0.45, label="Launch (N2L: a = F/m)")
        ax.axvspan(*res["coast_t"], color="#A9D08E", alpha=0.45, label="Coasting (N1L: v ≈ constant)")
        ax.axhline(0, color="black", lw=0.6)
        ax.grid(alpha=0.3)
    ax_v.set_ylabel("Velocity (m/s)")
    ax_a.set_ylabel("Acceleration (m/s²)")
    ax_a.set_xlabel("Time (s)")
    ax_v.legend(loc="lower right", fontsize=8)
    fig.suptitle(f"{name} — total mass {mass:.3f} kg   (launch a = {res['a_push']:.2f} m/s²)",
                 fontweight="bold")
    fig.tight_layout()
    fig.savefig(out_png, dpi=110)
    plt.close(fig)


def build_trial_workbook(name, run_num, weights, res, png, out_path):
    wb = Workbook()
    ws = wb.active
    ws.title = name
    ws["A1"] = f"{name} — Newton's 2nd Law trial (cart + {weights} weight{'s' if weights != 1 else ''})"
    ws["A1"].font = TITLE_FONT
    info = [
        ("Cart mass (kg)", CART_KG),
        ("Weight mass each (kg)", WEIGHT_KG),
        ("Weights added", weights),
        ("Total mass m (kg)", "=B3+B4*B5"),
        ("Launch method", "Plunger (same spring launcher every trial)"),
        ("Source", f"{name}.gambl, Data Set {run_num} (Cart G motion sensor)"),
        ("Launch window (s)", f"{res['push_t'][0]:.2f} – {res['push_t'][1]:.2f}"),
        ("Launch acceleration a (m/s²)", round(res["a_push"], 3)),
        ("  R² of launch v-t fit", round(res["r2_push"], 4)),
        ("Sensor's peak a (smoothed, m/s²)", round(res["sensor_peak_a"], 3)),
        ("Peak velocity (m/s)", round(res["vpk"], 3)),
        ("Coasting window (s)", f"{res['coast_t'][0]:.2f} – {res['coast_t'][1]:.2f}"),
        ("Coasting avg velocity (m/s)", round(res["v_coast"], 3)),
        ("Coasting acceleration (m/s²)", round(res["a_coast"], 3)),
    ]
    for i, (label, value) in enumerate(info, start=3):
        ws.cell(row=i, column=1, value=label).font = BOLD
        ws.cell(row=i, column=2, value=value)
    ws["A18"] = ("Launch a = slope of the velocity-time graph during the plunger push (orange rows). "
                 "Coasting rows (green) show v staying nearly constant once the push ends — Newton's 1st Law.")
    ws["A18"].alignment = Alignment(wrap_text=True, vertical="top")
    ws.merge_cells("A18:F19")
    ws.row_dimensions[18].height = 30

    start = 21
    header_row(ws, start, ["Time (s)", "Position (m)", "Velocity (m/s)", "Acceleration (m/s²)", "Phase"])
    for k, (i, p) in enumerate(enumerate(res["pts"]), start=start + 1):
        phase = "Launch" if i in res["push"] else "Coasting" if i in res["coast"] else ""
        fill = PUSH_FILL if phase == "Launch" else COAST_FILL if phase == "Coasting" else None
        for col, val in enumerate([p[0], p[1], p[2], p[3], phase], start=1):
            cell = ws.cell(row=k, column=col, value=val)
            if fill:
                cell.fill = fill
    ws.column_dimensions["A"].width = 30
    for col in "BCDE":
        ws.column_dimensions[col].width = 18
    img = XLImage(png)
    img.width, img.height = 620, 504
    ws.add_image(img, "G3")
    wb.save(out_path)


def add_chart(ws, title, x_title, x_col, first, last, anchor, trend):
    ch = ScatterChart()
    ch.title, ch.style = title, 13
    ch.x_axis.title, ch.y_axis.title = x_title, "Launch acceleration a (m/s²)"
    ch.x_axis.delete = ch.y_axis.delete = False
    xs = Reference(ws, min_col=x_col, min_row=first, max_row=last)
    ys = Reference(ws, min_col=5, min_row=first, max_row=last)
    s = Series(ys, xs, title="Trials")
    s.marker.symbol, s.marker.size = "circle", 8
    s.graphicalProperties.line.noFill = True
    if trend:
        s.trendline = Trendline(trendlineType=trend, dispEq=True, dispRSqr=True)
    ch.series.append(s)
    ch.legend = None
    ch.width, ch.height = 16, 8.5
    ws.add_chart(ch, anchor)


def build_results_workbook(rows, png, out_path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Results"
    ws["A1"] = "Newton's 2nd Law — acceleration vs. mass (constant launch force)"
    ws["A1"].font = TITLE_FONT
    ws["A2"] = ("Same plunger launch every trial; mass increased by adding 142 g weights to the 292 g cart. "
                "Prediction: a = F·(1/m), so a vs 1/m should be a straight line with slope = F. "
                "Launch a = slope of v-t during the push; the sensor's own acceleration curve is smoothed, "
                "so its peak (last column) reads lower but shows the same trend.")
    hdr = ["Trial", "Weights added", "Total mass m (kg)", "1/m (1/kg)", "Launch a (m/s²)",
           "F = m·a (N)", "Peak v (m/s)", "Coasting v (m/s)", "Coasting a (m/s²)",
           "Sensor peak a (m/s²)"]
    header_row(ws, 4, hdr)
    ws.row_dimensions[4].height = 32
    first = 5
    for r, row in enumerate(rows, start=first):
        ws.cell(row=r, column=1, value=row["name"])
        ws.cell(row=r, column=2, value=row["weights"])
        ws.cell(row=r, column=3, value=f"={CART_KG}+B{r}*{WEIGHT_KG}")
        ws.cell(row=r, column=4, value=f"=1/C{r}")
        ws.cell(row=r, column=5, value=round(row["a_push"], 3))
        ws.cell(row=r, column=6, value=f"=C{r}*E{r}")
        ws.cell(row=r, column=7, value=round(row["vpk"], 3))
        ws.cell(row=r, column=8, value=round(row["v_coast"], 3))
        ws.cell(row=r, column=9, value=round(row["a_coast"], 3))
        ws.cell(row=r, column=10, value=round(row["sensor_peak_a"], 3))
        for col in (3, 4, 6):
            ws.cell(row=r, column=col).number_format = "0.000"
    last = first + len(rows) - 1

    fit_row = last + 2
    ws.cell(row=fit_row, column=1, value="Best-fit line: a vs 1/m").font = BOLD
    fits = [("Slope (= launch force F, N)", f"=SLOPE(E{first}:E{last},D{first}:D{last})"),
            ("Intercept (m/s²)", f"=INTERCEPT(E{first}:E{last},D{first}:D{last})"),
            ("R²", f"=RSQ(E{first}:E{last},D{first}:D{last})"),
            ("Correlation a vs m (negative = inverse)", f"=CORREL(E{first}:E{last},C{first}:C{last})")]
    for k, (label, formula) in enumerate(fits, start=fit_row + 1):
        ws.cell(row=k, column=1, value=label)
        ws.cell(row=k, column=3, value=formula).number_format = "0.000"
    for col, width in zip("ABCDEFGHIJ", [38, 10, 14, 12, 14, 12, 12, 14, 14, 14]):
        ws.column_dimensions[col].width = width

    add_chart(ws, "Acceleration vs Mass (inverse)", "Total mass m (kg)", 3, first, last, "L4", trend=None)
    add_chart(ws, "Acceleration vs 1/Mass (linearized)", "1/m (1/kg)", 4, first, last, "L22", trend="linear")
    img = XLImage(png)
    img.width, img.height = 880, 360
    ws.add_image(img, f"A{fit_row + 7}")
    wb.save(out_path)


def plot_summary(rows, out_png):
    m = [CART_KG + r["weights"] * WEIGHT_KG for r in rows]
    a = [r["a_push"] for r in rows]
    inv = [1 / x for x in m]
    slope, icpt, r2 = linfit(inv, a)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))
    ax1.plot(m, a, "o", color="#1F6F6F", ms=8)
    ax1.set(xlabel="Total mass m (kg)", ylabel="Launch acceleration a (m/s²)", title="a vs m — inverse")
    ax2.plot(inv, a, "o", color="#1F6F6F", ms=8)
    xs = [0, max(inv) * 1.05]
    ax2.plot(xs, [slope * x + icpt for x in xs], "--", color="#C00000",
             label=f"a = {slope:.3f}(1/m) + {icpt:.3f}\nR² = {r2:.3f}")
    ax2.set(xlabel="1/m (1/kg)", ylabel="Launch acceleration a (m/s²)", title="a vs 1/m — linearized")
    ax2.legend(fontsize=9)
    for ax in (ax1, ax2):
        ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_png, dpi=120)
    plt.close(fig)
    return slope, icpt, r2


def main(out_dir):
    graphs = os.path.join(out_dir, "Graphs")
    os.makedirs(graphs, exist_ok=True)
    runs = read_runs(os.path.join(DOCS, "N2L_5.gambl"))
    rows = []
    for name, run_num, weights in TRIALS:
        res = analyze(runs[run_num - 1])
        mass = CART_KG + weights * WEIGHT_KG
        png = os.path.join(graphs, f"{name} - velocity and acceleration.png")
        plot_trial(name, mass, res, png)
        build_trial_workbook(name, run_num, weights, res, png,
                             os.path.join(out_dir, f"{name} Trial ({weights} weight{'' if weights == 1 else 's'}).xlsx"))
        rows.append({"name": name, "weights": weights, **res})
        print(f"{name}: m={mass:.3f} a={res['a_push']:.3f} (R2 {res['r2_push']:.3f}) "
              f"vpk={res['vpk']:.3f} coast v={res['v_coast']:.3f} coast a={res['a_coast']:.3f} "
              f"push {res['push_t']} coast {res['coast_t']} m*a={mass * res['a_push']:.3f}")
    summary_png = os.path.join(graphs, "N2L Results - a vs m and a vs 1-m.png")
    slope, icpt, r2 = plot_summary(rows, summary_png)
    build_results_workbook(rows, summary_png, os.path.join(out_dir, "N2L Results - Acceleration vs Mass.xlsx"))
    print(f"a vs 1/m fit: slope={slope:.3f} intercept={icpt:.3f} R2={r2:.3f}")


if __name__ == "__main__":
    main(sys.argv[1])
