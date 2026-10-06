#!/usr/bin/env python3
"""
Render an HTML file to a print-ready PDF for Neutrinos print media.

Primary engine: WeasyPrint (great CSS @page / print support, embeds fonts).
Fallback: headless Chromium via Playwright, if WeasyPrint is unavailable.

The bundled Poppins fonts are registered automatically so `font-family: "Poppins"`
resolves even if Poppins is not installed system-wide. Point --fonts at the
brand-core fonts folder if your HTML does not already @font-face them.

Usage:
    python html_to_pdf.py input.html output.pdf
    python html_to_pdf.py input.html output.pdf --fonts /path/to/assets/fonts
    python html_to_pdf.py input.html output.pdf --engine chromium

Dependency policy (never pollutes the system interpreter):
- Uses an already-importable WeasyPrint if present.
- Otherwise, if --allow-install is given, installs WeasyPrint into a dedicated
  venv at ~/.cache/neutrinos-designer/venv (created with `uv venv` when
  available, else `python -m venv`) and re-executes itself there.
- Without --allow-install, prints exact setup instructions and exits non-zero.

Notes:
- Set page size / margins / bleed in your CSS via @page (e.g. `@page{size:A4;margin:18mm}`).
- For commercial print add 3mm bleed and keep text inside a safe margin.
- Prefer the per-lockup logo PNGs (or a single-lockup SVG from tools/split_logo_svg.py)
  for crisp output; the bundled artboard SVG is not a placeable asset.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

VENV_DIR = Path.home() / ".cache" / "neutrinos-designer" / "venv"


def _default_fonts_dir(script_path: Path) -> Path:
    # scripts/ -> neutrinos-print/ -> skills/ -> neutrinos-brand-core/assets/fonts
    return script_path.parent.parent.parent / "neutrinos-brand-core" / "assets" / "fonts"


def render_weasyprint(html_path: Path, pdf_path: Path, fonts_dir: Path | None) -> bool:
    try:
        from weasyprint import HTML  # noqa
        from weasyprint.text.fonts import FontConfiguration  # noqa
    except Exception:
        return False

    font_config = FontConfiguration()
    extra_css = None
    if fonts_dir and fonts_dir.is_dir():
        faces = []
        weight_map = {
            "Poppins-Light.ttf": (300, "normal"),
            "Poppins-LightItalic.ttf": (300, "italic"),
            "Poppins-Regular.ttf": (400, "normal"),
            "Poppins-Medium.ttf": (500, "normal"),
            "Poppins-SemiBold.ttf": (600, "normal"),
            "Poppins-SemiBoldItalic.ttf": (600, "italic"),
        }
        for fname, (wght, style) in weight_map.items():
            fpath = fonts_dir / fname
            if fpath.exists():
                faces.append(
                    f'@font-face{{font-family:"Poppins";font-weight:{wght};'
                    f'font-style:{style};src:url("file://{fpath.as_posix()}") format("truetype");}}'
                )
        if faces:
            from weasyprint import CSS
            extra_css = CSS(string="\n".join(faces), font_config=font_config)

    stylesheets = [extra_css] if extra_css else None
    HTML(filename=str(html_path), base_url=str(html_path.parent)).write_pdf(
        str(pdf_path), stylesheets=stylesheets, font_config=font_config
    )
    return True


def render_chromium(html_path: Path, pdf_path: Path) -> bool:
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return False
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(html_path.resolve().as_uri())
        page.emulate_media(media="print")
        page.pdf(path=str(pdf_path), prefer_css_page_size=True, print_background=True)
        browser.close()
    return True


def setup_venv_weasyprint() -> int:
    """Install WeasyPrint into a dedicated venv and re-exec this script there.

    Returns 0 on success (after re-exec, which never returns), non-zero on failure.
    Never touches the system interpreter."""
    print(f"WeasyPrint not found. Setting up isolated venv at {VENV_DIR} ...")
    if not VENV_DIR.exists():
        uv = _which_uv()
        if uv:
            rc = subprocess.run([uv, "venv", str(VENV_DIR), "--clear", "-q"]).returncode
            if rc != 0:
                return 1
        else:
            rc = subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)]).returncode
            if rc != 0:
                return 1
    pip = VENV_DIR / "bin" / "pip"
    rc = subprocess.run([str(pip), "install", "-q", "weasyprint"]).returncode
    if rc != 0:
        return 1
    print("Re-running in the venv ...")
    os.execv(str(VENV_DIR / "bin" / "python"),
             [str(VENV_DIR / "bin" / "python"), __file__] + sys.argv[1:])


def _which_uv() -> str | None:
    from shutil import which
    return which("uv")


def main() -> int:
    ap = argparse.ArgumentParser(description="Render HTML to a print-ready PDF (Neutrinos).")
    ap.add_argument("input", type=Path, help="input .html file")
    ap.add_argument("output", type=Path, help="output .pdf file")
    ap.add_argument("--fonts", type=Path, default=None, help="folder with Poppins TTFs")
    ap.add_argument("--engine", choices=["auto", "weasyprint", "chromium"], default="auto")
    ap.add_argument("--allow-install", action="store_true",
                    help="allow creating ~/.cache/neutrinos-designer/venv and installing "
                         "WeasyPrint there (never the system interpreter)")
    args = ap.parse_args()

    if not args.input.exists():
        print(f"error: input not found: {args.input}", file=sys.stderr)
        return 2

    fonts_dir = args.fonts or _default_fonts_dir(Path(__file__).resolve())

    if args.engine in ("auto", "weasyprint"):
        if render_weasyprint(args.input, args.output, fonts_dir):
            print(f"OK (weasyprint): {args.output}")
            return 0
        if args.allow_install:
            setup_venv_weasyprint()  # never returns on success
            print("error: venv setup failed", file=sys.stderr)
            return 1

    if args.engine in ("auto", "chromium"):
        if render_chromium(args.input, args.output):
            print(f"OK (chromium): {args.output}")
            return 0

    print(
        "Could not render. Options:\n"
        "  1. Re-run with --allow-install to set up an isolated venv with WeasyPrint\n"
        "     (at ~/.cache/neutrinos-designer/venv, system Python untouched), or\n"
        "  2. set up manually:\n"
        "        uv venv ~/.cache/neutrinos-designer/venv\n"
        "        ~/.cache/neutrinos-designer/venv/bin/pip install weasyprint\n"
        "        ~/.cache/neutrinos-designer/venv/bin/python "
        f"{Path(__file__).name} {args.input} {args.output}\n"
        "  3. use headless Chromium: pip install playwright && playwright install chromium\n"
        "Your HTML with @page CSS will work with either engine.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
