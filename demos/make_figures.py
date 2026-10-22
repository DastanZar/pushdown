"""Generate offline visuals from measured receipt traces, never invented data."""

import json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw

matplotlib.use("Agg")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets"
OUT.mkdir(exist_ok=True)
r = json.loads((ROOT / "receipts" / "receipt.json").read_text())
plt.rcParams.update({"font.family": "DejaVu Sans", "figure.dpi": 150, "font.size": 10})


def save(name):
    plt.tight_layout()
    plt.savefig(OUT / name)
    plt.close()


def frames_gif(rows, lines, name, accent):
    frames = []
    for index, row in enumerate(rows):
        image = Image.new("RGB", (850, 280), "#0f172a")
        draw = ImageDraw.Draw(image)
        draw.text(
            (28, 22),
            f"{ROOT.name} | live-code trace | step {index + 1}/{len(rows)}",
            fill=accent,
            font_size=23,
        )
        for j, line in enumerate(lines(row)):
            draw.text((28, 80 + j * 38), line, fill="#e2e8f0", font_size=20)
        draw.rectangle((28, 250, 28 + int(780 * (index + 1) / len(rows)), 258), fill=accent)
        frames.append(image)
    frames[0].save(OUT / name, save_all=True, append_images=frames[1:], duration=500, loop=0)


rows = r["depth_scaling"]
plt.figure(figsize=(8, 4))
plt.plot(
    [x["depth"] for x in rows],
    [x["pda"]["median_us"] for x in rows],
    "o-",
    label="Python explicit stack",
)
std = [x for x in rows if "stdlib" in x]
plt.plot(
    [x["depth"] for x in std],
    [x["stdlib"]["median_us"] for x in std],
    "o-",
    label="CPython json.loads",
)
plt.xscale("log")
plt.yscale("log")
plt.xlabel("Nesting depth")
plt.ylabel("Median parse time (microseconds; 7 runs)")
plt.title("Depth has a cost: measured CPU parsing, not a speedup claim")
plt.legend()
save("depth_timing.png")

plt.figure(figsize=(8, 3))
plt.plot([x["depth"] for x in rows], [x["pda_accepts"] for x in rows], "o-", label="Explicit stack")
plt.plot(
    [x["depth"] for x in rows],
    [x["synthetic_cap3_accepts"] for x in rows],
    "s--",
    label="Synthetic cap=3 (same parser)",
)
plt.xscale("log")
plt.yticks([0, 1], ["reject", "accept"])
plt.xlabel("Nesting depth; no production decoder measured")
plt.title("A configured cap rejects deeper documents by construction")
plt.legend()
save("cliff.png")

plt.figure(figsize=(8, 3))
plt.bar(
    [x["state"] for x in r["selectivity"]], [x["kept"] for x in r["selectivity"]], color="#3569ab"
)
plt.ylabel("Allowed renderings / 103")
plt.title("Syntax-only mask selectivity on a toy Unicode vocabulary")
save("selectivity.png")

plt.figure(figsize=(8, 3))
plt.step([x["step"] for x in r["trace"]], [len(x["stack"]) for x in r["trace"]], where="post")
plt.xlabel("Characters consumed")
plt.ylabel("Open containers")
plt.title("Observed stack depth for a nested object/array")
save("stack_depth.png")
frames_gif(
    r["trace"],
    lambda row: [
        "Input: " + repr(row["char"]),
        "Mode: " + row["mode"],
        "Stack: " + (" / ".join(row["stack"]) or "empty"),
    ],
    "parse_trace.gif",
    "#60a5fa",
)
