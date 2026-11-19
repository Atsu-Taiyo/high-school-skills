#!/usr/bin/env python3
"""SVG を PNG にする（目視確認用）。

    python3 render_png.py fig.svg [fig2.svg ...] [-o 出力フォルダ] [--scale 2] [--renderer auto]

レンダラーは次の順に探す（--renderer で指定もできる）。
  1. chrome    Chrome / Chromium のヘッドレス。SVG を <img> で読む HTML を経由して撮る。
               ブラウザと同じ描画になるので，これを第一候補にする。
               macOS は /Applications の Google Chrome・Chromium，
               Linux は google-chrome / google-chrome-stable / chromium / chromium-browser を探す。
  2. rsvg      rsvg-convert（librsvg）。
  3. cairosvg  簡易確認用。<tspan> を含む文字列（斜体と立体を混ぜた式，添字など）の
               位置を崩して描くことがある。文字の位置はこの結果で判断しない。
  4. resvg / inkscape / macOS の qlmanage（最後の手段）

どれも無ければ導入方法を表示して終了コード 2 で終わる。
PNG は SVG と同じ名前（拡張子 .png）で，-o を省くと SVG の隣に作る。
"""
import argparse
import os
import pathlib
import re
import shutil
import subprocess
import time
import sys
import tempfile
import xml.etree.ElementTree as ET

HELP = """PNG 化の手段が見つからない。次のどれかを用意する（上ほど望ましい）。
  1. Google Chrome か Chromium を入れる（ヘッドレスで撮る。ブラウザと同じ描画）
  2. rsvg-convert（macOS: brew install librsvg，Debian 系: apt install librsvg2-bin）
  3. cairosvg（簡易確認用。tspan を含む文字の位置が崩れることがある）
       uv を使う場合:   uv run --with cairosvg python3 render_png.py fig.svg
       venv を使う場合: python3 -m venv .venv && .venv/bin/pip install cairosvg
     cairo 本体も必要（macOS: brew install cairo，Debian 系: apt install libcairo2）"""

_REEXEC = "HSFIG_RENDER_REEXEC"
_MAC_CHROME = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)
_LINUX_CHROME = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")


def find_chrome():
    env = os.environ.get("CHROME")
    if env and (os.path.exists(env) or shutil.which(env)):
        return env
    if sys.platform == "darwin":
        for p in _MAC_CHROME:
            p = os.path.expanduser(p)
            if os.path.exists(p):
                return p
    for name in _LINUX_CHROME:
        p = shutil.which(name)
        if p:
            return p
    return None


def svg_size(path):
    """SVG の表示サイズ（CSS px）。width/height が無ければ viewBox から取る。"""
    root = ET.parse(path).getroot()

    def px(v):
        m = re.fullmatch(r"\s*([\d.]+)\s*(px|mm|cm|in|pt)?\s*", v or "")
        if not m:
            return None
        k = {"px": 1, None: 1, "mm": 96 / 25.4, "cm": 96 / 2.54, "in": 96, "pt": 96 / 72}[m.group(2)]
        return float(m.group(1)) * k

    w, h = px(root.get("width")), px(root.get("height"))
    vb = [float(t) for t in re.split(r"[\s,]+", (root.get("viewBox") or "").strip()) if t]
    if len(vb) == 4:
        if w is None and h is None:
            w, h = vb[2], vb[3]
        elif w is None:
            w = h * vb[2] / vb[3]
        elif h is None:
            h = w * vb[3] / vb[2]
    return (w or 300.0), (h or 150.0)


def by_chrome(chrome, src, dst, scale):
    w, h = svg_size(src)
    W, H = int(-(-w // 1)), int(-(-h // 1))
    with tempfile.TemporaryDirectory(prefix="hsfig-") as tmp:
        html = os.path.join(tmp, "page.html")
        uri = pathlib.Path(src).resolve().as_uri()
        with open(html, "w", encoding="utf-8") as fh:
            fh.write('<!doctype html><meta charset="utf-8">'
                     "<style>html,body{margin:0;background:#fff}img{display:block}</style>"
                     f'<img src="{uri}" width="{w:g}" height="{h:g}">')
        out = os.path.abspath(dst)
        cmd = [chrome, "--headless=new", f"--screenshot={out}", f"--window-size={W},{H}",
               f"--force-device-scale-factor={scale:g}", "--hide-scrollbars", "--disable-gpu",
               "--no-first-run", "--allow-file-access-from-files",
               f"--user-data-dir={os.path.join(tmp, 'profile')}", pathlib.Path(html).as_uri()]
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            cmd.insert(1, "--no-sandbox")
        # Chrome は撮影後の終了処理で固まることがある。PNG が書き出されて大きさが落ち着いたら，
        # 終了を待たずに止める（撮影そのものは数秒で終わる）。
        if os.path.exists(out):
            os.remove(out)
        log = open(os.path.join(tmp, "chrome.log"), "wb")
        proc = subprocess.Popen(cmd, stdout=log, stderr=log)
        t0, last, stable = time.time(), -1, 0
        while proc.poll() is None and time.time() - t0 < 120:
            time.sleep(0.5)
            size = os.path.getsize(out) if os.path.exists(out) else -1
            stable = stable + 1 if size > 0 and size == last else 0
            last = size
            if stable >= 4:
                break
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        log.close()
        if not os.path.exists(out) or os.path.getsize(out) == 0:
            with open(os.path.join(tmp, "chrome.log"), "rb") as fh:
                raise RuntimeError("Chrome のヘッドレス撮影に失敗: " + fh.read().decode(errors="replace")[-400:])


def load_cairosvg():
    try:
        import cairosvg
        return cairosvg
    except ImportError:
        return None
    except OSError:
        # macOS: Homebrew の cairo が既定の検索パスに無い場合は，パスを足して1回だけやり直す
        if sys.platform == "darwin" and not os.environ.get(_REEXEC):
            for lib in ("/opt/homebrew/lib", "/usr/local/lib"):
                if os.path.exists(os.path.join(lib, "libcairo.2.dylib")):
                    env = dict(os.environ, **{_REEXEC: "1"})
                    old = env.get("DYLD_FALLBACK_LIBRARY_PATH", "")
                    env["DYLD_FALLBACK_LIBRARY_PATH"] = lib + (":" + old if old else "")
                    os.execve(sys.executable, [sys.executable] + sys.argv, env)
        return None


def pick(renderer):
    """使うレンダラーを (名前, 実体) で返す。無ければ (None, None)。"""
    want = (lambda n: renderer in ("auto", n))
    if want("chrome"):
        c = find_chrome()
        if c:
            return "chrome", c
    if want("rsvg") and shutil.which("rsvg-convert"):
        return "rsvg", "rsvg-convert"
    if want("cairosvg"):
        m = load_cairosvg()
        if m:
            return "cairosvg", m
    if renderer == "auto":
        for name in ("resvg", "inkscape"):
            if shutil.which(name):
                return name, name
        if sys.platform == "darwin" and shutil.which("qlmanage"):
            return "qlmanage", "qlmanage"
    return None, None


def main():
    ap = argparse.ArgumentParser(description="SVG を PNG にする（目視確認用）")
    ap.add_argument("svg", nargs="+")
    ap.add_argument("-o", "--outdir", help="出力フォルダ（省くと SVG の隣）")
    ap.add_argument("--scale", type=float, default=2.0, help="拡大率（既定 2）")
    ap.add_argument("--renderer", default="auto", choices=["auto", "chrome", "rsvg", "cairosvg"],
                    help="レンダラー（既定 auto: chrome → rsvg → cairosvg → その他）")
    args = ap.parse_args()

    name, tool = pick(args.renderer)
    if not name:
        print(HELP, file=sys.stderr)
        return 2
    print(f"renderer: {name}", file=sys.stderr)
    if name == "cairosvg":
        print("注意: cairosvg は tspan を含む文字列の位置を崩すことがある。"
              "文字の位置は Chrome か rsvg-convert の結果で確かめる。", file=sys.stderr)
    if args.outdir:
        os.makedirs(args.outdir, exist_ok=True)
    for src in args.svg:
        base = os.path.splitext(os.path.basename(src))[0] + ".png"
        dst = os.path.join(args.outdir or os.path.dirname(src) or ".", base)
        if name == "chrome":
            by_chrome(tool, src, dst, args.scale)
        elif name == "rsvg":
            subprocess.run(["rsvg-convert", "-b", "white", "-z", f"{args.scale:g}", src, "-o", dst], check=True)
        elif name == "cairosvg":
            tool.svg2png(url=src, write_to=dst, scale=args.scale, background_color="white")
        elif name == "resvg":
            subprocess.run(["resvg", "--background", "white", "-z", f"{args.scale:g}", src, dst], check=True)
        elif name == "inkscape":
            subprocess.run(["inkscape", src, "--export-type=png", f"--export-filename={dst}",
                            "--export-background=white", f"--export-dpi={96 * args.scale:g}"], check=True)
        else:
            out = os.path.dirname(dst) or "."
            subprocess.run(["qlmanage", "-t", "-s", "1200", "-o", out, src], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            os.replace(os.path.join(out, os.path.basename(src) + ".png"), dst)
            print("（qlmanage で代用。余白や大きさが実際と違うことがある）", file=sys.stderr)
        print(dst)
    return 0


if __name__ == "__main__":
    sys.exit(main())
