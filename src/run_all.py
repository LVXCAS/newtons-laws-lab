"""Run the whole pipeline: .gambl files in data/ -> CSV tables, PNG graphs and a slide deck in outputs/."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_angled  # noqa: E402
import build_n1l  # noqa: E402
import build_n2l  # noqa: E402
import build_n3l  # noqa: E402
import build_slides  # noqa: E402
import export_gambl  # noqa: E402

REQUIRED = ["ANGLED", "N2L_5", "N3L_6"] + [n for n, *_ in build_n2l.TRIALS] + export_gambl.SAVE_ORDER


def main():
    missing = sorted({f for f in REQUIRED if not os.path.exists(os.path.join(export_gambl.DATA_DIR, f + ".gambl"))})
    if missing:
        sys.exit(f"Missing .gambl files in {os.path.abspath(export_gambl.DATA_DIR)}: {', '.join(missing)}")
    out = build_slides.OUT_DIR
    export_gambl.main(os.path.join(out, "all_runs"))
    build_n2l.main(os.path.join(out, "n2l"))
    build_n1l.main(os.path.join(out, "n2l"), os.path.join(out, "n1l"))
    build_n3l.main(os.path.join(out, "n3l"))
    build_angled.main(os.path.join(out, "angled"))
    build_slides.main(os.path.join(out, "slides"))
    print("Done. Outputs in", os.path.abspath(out))


if __name__ == "__main__":
    main()
