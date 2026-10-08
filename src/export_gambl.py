"""Export Vernier Graphical Analysis (.gambl) runs to an Excel workbook + PNG graphs."""
import os
import sys
import tarfile
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

DATA_DIR = os.environ.get("GAMBL_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data"))
DOCS = DATA_DIR
# Each save of the session contains every earlier run, so a run belongs to the
# first file (in save order) that contains it.
SAVE_ORDER = ["N3L", "N3L_2", "N3L_3", "N3L_4", "N3L_5_7353", "N3L_6",
              "N2L_1", "N2L_2", "N2L_3", "N2L_4", "N2L_5", "ANGLED"]
SEPARATE = ["Untitled_4742"]
MOVING_SPEED = 0.02  # m/s; samples slower than this count as "cart at rest"
CART_COLORS = {"Y": "#C9A400", "G": "#1F6F6F"}
CAR_NAMES = {"G": "Car 1", "Y": "Car 2"}  # green/blue trace = Car 1, yellow = Car 2
HEADER_FILL = PatternFill("solid", fgColor="1F4E79")
HEADER_FONT = Font(bold=True, color="FFFFFF")


def to_number(cell):
    """Vernier writes 'Z1 1:' for a sample the sensor missed; keep it as a blank."""
    try:
        return float(cell)
    except ValueError:
        return None


def present(*series):
    """Zip series, dropping rows where any value is a missed sample."""
    return [row for row in zip(*series) if None not in row]


def read_runs(path):
    with tarfile.open(path) as tar:
        xml_bytes = tar.extractfile("vstudm/data.udm").read()
    root = ET.fromstring(xml_bytes)
    runs = []
    for ds in root.iter("DataSet"):
        cols = {}
        for col in ds.iter("DataColumn"):
            cells = [c for c in (col.findtext("ColumnCells") or "").split("\n") if c.strip()]
            if cells:
                name = f"{col.findtext('DataObjectName')} ({col.findtext('ColumnUnits')})"
                cols[name] = [to_number(c) for c in cells]
        if cols:
            runs.append({"name": ds.findtext("DataSetName"), "cols": cols})
    return runs


def carts(cols):
    return [c for c in ("G", "Y") if f"Position {c} (m)" in cols]


def summarize(run):
    cols = run["cols"]
    t = cols["Time (s)"]
    row = {"samples": len(t), "duration": round(t[-1] - t[0], 3)}
    for c in carts(cols):
        x, v, a = (cols[f"{q} {c} ({u})"] for q, u in
                   [("Position", "m"), ("Velocity", "m/s"), ("Acceleration", "m/s²")])
        xs, vs, accs = ([p for p in s if p is not None] for s in (x, v, a))
        if not xs:
            continue
        row[c] = {
            "x0": xs[0], "x1": xs[-1], "dx": xs[-1] - xs[0],
            "vmax": max(vs, key=abs),
            "amax": max(accs, key=abs),
            "missing": len(x) - len(xs),
        }
    moved = any(abs(row[c]["vmax"]) > MOVING_SPEED * 5 for c in ("Y", "G") if c in row)
    row["note"] = "" if moved else "No motion recorded (false start?)"
    return row


def plot_run(run, title, out_png):
    cols = run["cols"]
    t = cols["Time (s)"]
    fig, axes = plt.subplots(3, 1, figsize=(8, 7.5), sharex=True)
    for ax, qty, unit in zip(axes, ["Position", "Velocity", "Acceleration"], ["m", "m/s", "m/s²"]):
        for c in carts(cols):
            pts = present(t, cols[f"{qty} {c} ({unit})"])
            if pts:
                ax.plot(*zip(*pts), color=CART_COLORS[c], lw=1.8, label=CAR_NAMES[c])
        ax.axhline(0, color="black", lw=0.6)
        ax.set_ylabel(f"{qty} ({unit})")
        ax.grid(alpha=0.3)
    if axes[0].get_legend_handles_labels()[0]:
        axes[0].legend(loc="best", fontsize=8)
    axes[-1].set_xlabel("Time (s)")
    fig.suptitle(title, fontweight="bold")
    fig.tight_layout()
    fig.savefig(out_png, dpi=110)
    plt.close(fig)


def style_header(ws, row, ncols):
    for i in range(1, ncols + 1):
        cell = ws.cell(row=row, column=i)
        cell.fill, cell.font = HEADER_FILL, HEADER_FONT
        cell.alignment = Alignment(horizontal="center", wrap_text=True)


def write_run_sheet(wb, sheet_name, title, run, png):
    ws = wb.create_sheet(sheet_name)
    ws["A1"] = title
    ws["A1"].font = Font(bold=True, size=13)
    headers = list(run["cols"].keys())
    ws.append([])
    ws.append(headers)
    style_header(ws, 3, len(headers))
    for i in range(len(run["cols"]["Time (s)"])):
        ws.append([run["cols"][h][i] for h in headers])
    for i in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(i)].width = 17
    ws.freeze_panes = "A4"
    img = XLImage(png)
    img.width, img.height = 640, 600
    ws.add_image(img, f"{get_column_letter(len(headers) + 2)}3")


def main(out_dir):
    png_dir = os.path.join(out_dir, "Graphs")
    os.makedirs(png_dir, exist_ok=True)

    all_runs = read_runs(os.path.join(DOCS, "ANGLED.gambl"))
    first_file, seen = {}, 0
    for f in SAVE_ORDER:
        n = len(read_runs(os.path.join(DOCS, f + ".gambl")))
        for i in range(seen, n):
            first_file[i] = f
        seen = max(seen, n)

    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws["A1"] = "Newton's Laws Lab — Vernier Graphical Analysis data (exported)"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = ("Cart Y = yellow trace, Cart G = green trace. Peak v / peak a = largest-magnitude value "
                "the sensor recorded (sign kept). Click a run number to jump to its data + graph.")
    hdr = ["Run", "Saved in file", "Samples", "Duration (s)"]
    for c in ("Y", "G"):
        hdr += [f"Cart {c} start x (m)", f"Cart {c} end x (m)", f"Cart {c} Δx (m)",
                f"Cart {c} peak v (m/s)", f"Cart {c} peak a (m/s²)", f"Cart {c} missed samples"]
    hdr.append("Note")
    ws.append([])
    ws.append(hdr)
    style_header(ws, 4, len(hdr))
    ws.row_dimensions[4].height = 45

    for i, run in enumerate(all_runs):
        num = i + 1
        src = first_file.get(i, "ANGLED")
        title = f"Run {num} — {run['name']} (from {src}.gambl)"
        png = os.path.join(png_dir, f"Run {num:02d} ({src}).png")
        plot_run(run, title, png)
        write_run_sheet(wb, f"Run {num}", title, run, png)
        s = summarize(run)
        row = [num, src + ".gambl", s["samples"], s["duration"]]
        for c in ("Y", "G"):
            d = s.get(c)
            row += [round(d["x0"], 4), round(d["x1"], 4), round(d["dx"], 4),
                    round(d["vmax"], 4), round(d["amax"], 4), d["missing"]] if d else ["no data"] + [None] * 5
        row.append(s["note"])
        ws.append(row)
        ws.cell(row=ws.max_row, column=1).hyperlink = f"#'Run {num}'!A1"
        ws.cell(row=ws.max_row, column=1).font = Font(color="0563C1", underline="single")

    for i in range(1, len(hdr) + 1):
        ws.column_dimensions[get_column_letter(i)].width = 14 if i > 2 else 16
    ws.freeze_panes = "B5"

    for f in SEPARATE:
        if not os.path.exists(os.path.join(DOCS, f + ".gambl")):
            continue
        for j, run in enumerate(read_runs(os.path.join(DOCS, f + ".gambl"))):
            title = f"{f}.gambl — {run['name']} (Oct 5, separate file)"
            png = os.path.join(png_dir, f"{f} set {j + 1}.png")
            plot_run(run, title, png)
            write_run_sheet(wb, f"Untitled set {j + 1}", title, run, png)

    out = os.path.join(out_dir, "Newtons Laws Lab Data.xlsx")
    wb.save(out)
    print("saved", out, "runs:", len(all_runs))


if __name__ == "__main__":
    main(sys.argv[1])
