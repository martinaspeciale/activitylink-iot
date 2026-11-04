"""Generate English report figures from the preserved hardware measurements"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "results/2026-11-02-final/stress"
OUT = Path(__file__).resolve().parent / "assets-en"
OUT.mkdir(parents=True, exist_ok=True)
runs = json.loads((EVIDENCE / "summary.json").read_text())["runs"]
plt.rcParams.update({"font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "pdf.fonttype": 42,
                     "axes.labelcolor": "#233b4d", "text.color": "#233b4d"})

# Recompute the plotted totals from individual runs without changing archived evidence
fig, axes = plt.subplots(1, 2, figsize=(9, 3.1), layout="constrained")
for index, (mode, color) in enumerate([(1, "#216b8b"), (0, "#b16b3c")]):
    group = [run for run in runs if run["adaptive"] == mode]
    stale = sum(run["stale_samples"] for run in group)
    red = sum(run["stale_command_red"] for run in group)
    percent = 100 * red / stale
    axes[0].bar(index, percent, color=color, width=0.5)
    axes[0].text(index, percent + 4, f"{red}/{stale}", ha="center", weight="bold")
    axes[1].scatter([index - .08, index, index + .08],
                    [run["detection_seconds_from_last_forwarded"] for run in group],
                    color=color, s=45)
axes[0].set(xticks=[0, 1], xticklabels=["Adaptive", "Baseline"], ylim=(0, 118),
            ylabel="Red commands during stale data (%)", title="Response to missing data")
axes[1].set(xticks=[0, 1], xticklabels=["Adaptive", "Baseline"], ylim=(0, 8),
            ylabel="Seconds since last forwarded sample", title="Detection: three runs per mode")
axes[1].axhline(6, color="#899aa3", linestyle="--", linewidth=1)
for axis in axes:
    axis.grid(axis="y", alpha=.18)
    axis.set_axisbelow(True)
fig.savefig(OUT / "stress-comparison.pdf")
plt.close(fig)

fig, axes = plt.subplots(2, 1, figsize=(9, 4.1), sharex=True, layout="constrained")
for axis, name, title in zip(axes, ["pair-1-adaptive", "pair-1-baseline"],
                            ["Adaptive", "Baseline"]):
    folder = EVIDENCE / name
    run = json.loads((folder / "summary.json").read_text())
    rows = json.loads((folder / "metrics.json").read_text())
    seconds = [row["time"] - run["start"] for row in rows]
    axis.axvspan(10, 25, color="#e8c6a4", alpha=.5, label="HAR telemetry withheld")
    axis.step(seconds, [row["command_led"] for row in rows], where="post",
              color="#216b8b", label="SQL-based command", linewidth=1.7)
    axis.plot(seconds, [row["reported_led"] for row in rows], ".",
              color="#a64636", label="Reported feedback", markersize=4)
    axis.set(title=title, yticks=[0, 1, 2, 3],
             yticklabels=["Off", "Green", "Blue", "Red"], ylim=(-.15, 3.3))
    axis.grid(axis="y", alpha=.18)
axes[0].legend(loc="lower right", ncols=3, fontsize=8)
axes[-1].set(xlabel="Time since run start (s)", xlim=(0, 40))
fig.savefig(OUT / "stress-timeline.pdf")
plt.close(fig)

fig, axis = plt.subplots(figsize=(10, 2.9), layout="constrained")
axis.set(xlim=(-0.3, 10), ylim=(-0.15, 3.05))
axis.axis("off")
boxes = [(0, 1.9, 1.6, .8, "HAR / node1\nLocal SVM + LED"),
         (0, .25, 1.6, .8, "Feedback / node2\nLED + watchdog"),
         (2.3, 1.08, 1.7, .8, "Border router\nRPL + USB/SLIP"),
         (4.7, 1.08, 1.5, .8, "Mosquitto\nMQTT broker"),
         (7, 1.9, 2.5, .8, "Python backend\nValidation + control"),
         (7, .25, 1.1, .8, "MySQL"),
         (8.6, .25, 1.1, .8, "Grafana")]
for x, y, width, height, label in boxes:
    axis.add_patch(FancyBboxPatch((x, y), width, height,
                                  boxstyle="round,pad=0.03,rounding_size=0.06",
                                  facecolor="#eff5f7", edgecolor="#216b8b"))
    axis.text(x + width / 2, y + height / 2, label, ha="center", va="center", fontsize=9)
for start, end in [((1.65, 2.2), (2.25, 1.65)), ((1.65, .75), (2.25, 1.3)),
                   ((4.05, 1.48), (4.65, 1.48)), ((6.25, 1.6), (6.95, 2.2)),
                   ((7.55, 1.85), (7.55, 1.1)), ((8.15, .65), (8.55, .65))]:
    axis.add_patch(FancyArrowPatch(start, end, arrowstyle="<->", mutation_scale=10,
                                   color="#216b8b", linewidth=1.2))
axis.text(.9, .02, "IEEE 802.15.4 / 6LoWPAN", fontsize=8, ha="center")
axis.text(5.6, .3, "Services on the Mac", fontsize=9, ha="center", weight="bold")
fig.savefig(OUT / "architecture.pdf", bbox_inches="tight", pad_inches=0.15)
plt.close(fig)
print("English figures generated from archived measurements")
