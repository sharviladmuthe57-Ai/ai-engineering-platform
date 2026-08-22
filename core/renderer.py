"""
renderer.py  —  Floor Plan Layout Renderer v2
==============================================
Draws:
  - Original floor plan (left panel)
  - AI electrical layout with proper symbols (right panel)
  - Wall outlines, room fills, door arcs, window markers
  - Wire routes colour-coded by circuit type
  - BOM table inset
  - Warnings box
  - Legend
Uses symbols.py for all electrical components.
"""

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
import matplotlib.image as mpimg
from matplotlib.lines import Line2D
from matplotlib.patches import Arc
import numpy as np

from .symbols import draw_symbol, SYMBOL_COLORS
from .geometry import ROOM_FILL

# ── PALETTE ───────────────────────────────────────────────────────────────
DARK   = "#0D1117"
PANEL  = "#161B22"
WHITE  = "#E6EDF3"
MUTED  = "#8B949E"
BORDER = "#30363D"

# Wire colour per circuit (by symbol type)
WIRE_COLOR = {
    "light"  : "#F1C40F",
    "fan"    : "#1ABC9C",
    "exhaust": "#2ECC71",
    "switch" : "#3498DB",
    "switch2": "#5DADE2",
    "outlet" : "#E74C3C",
    "outlet2": "#EC7063",
    "ac"     : "#9B59B6",
    "geyser" : "#E67E22",
    "tv"     : "#8E44AD",
    "wifi"   : "#2980B9",
    "db"     : "#E74C3C",
    "default": "#BDC3C7",
}


# ═════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═════════════════════════════════════════════════════════════════════════════
def render_layout(layout: dict, output_path: str,
                  original_image_path: str = None) -> str:

    rooms    = layout["rooms"]
    placed   = layout["placed_components"]
    routes   = layout["wire_routes"]
    cctv     = layout["cctv_components"]
    c_routes = layout["cctv_routes"]
    bom      = layout["bom"]
    warnings = layout["warnings"]
    db_pos   = layout.get("db_pos")
    nvr_pos  = layout.get("nvr_pos")

    # ── BOUNDS ─────────────────────────────────────────────────────────────
    if rooms:
        all_x = [r["x"] for r in rooms] + [r["x"]+r["width"]  for r in rooms]
        all_y = [r["y"] for r in rooms] + [r["y"]+r["height"] for r in rooms]
        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)
    else:
        min_x, max_x, min_y, max_y = 0, 15, 0, 12

    W = max(max_x - min_x, 1)
    H = max(max_y - min_y, 1)

    has_orig = (original_image_path is not None)
    n_cols   = 2 if has_orig else 1
    fw       = 16 * n_cols
    fig, axes = plt.subplots(1, n_cols, figsize=(fw, 11))
    fig.patch.set_facecolor(DARK)
    if n_cols == 1:
        axes = [axes]

    # ── LEFT: ORIGINAL IMAGE ───────────────────────────────────────────────
    if has_orig:
        ax0 = axes[0]
        ax0.set_facecolor(DARK)
        try:
            img = mpimg.imread(original_image_path)
            ax0.imshow(img, extent=[min_x, max_x, min_y, max_y],
                       origin="upper", alpha=0.92)
        except Exception:
            ax0.text((min_x+max_x)/2, (min_y+max_y)/2,
                     "Original plan", color=WHITE, ha="center", fontsize=12)
        _setup_ax(ax0, "INPUT — Uploaded Floor Plan", min_x, max_x, min_y, max_y)
        _draw_grid(ax0, min_x, max_x, min_y, max_y)

    # ── RIGHT: ELECTRICAL LAYOUT ───────────────────────────────────────────
    ax = axes[-1]
    ax.set_facecolor(DARK)
    _draw_grid(ax, min_x, max_x, min_y, max_y)

    # Rooms
    for room in rooms:
        _draw_room(ax, room)

    # Wire routes
    _draw_wire_routes(ax, routes, cctv_routes=c_routes)

    # Electrical components
    for comp in placed:
        x, y = comp["pos"]
        sym  = comp.get("symbol","outlet")
        draw_symbol(ax, sym, x, y, sz=_sym_size(W, H), zorder=8)

    # NVR box
    if nvr_pos:
        draw_symbol(ax, "db", nvr_pos[0], nvr_pos[1],
                    sz=_sym_size(W, H)*0.9, zorder=8)

    # CCTV cameras
    for cam in cctv:
        draw_symbol(ax, "camera", cam["pos"][0], cam["pos"][1],
                    sz=_sym_size(W, H), zorder=8)

    # BOM inset
    _draw_bom(ax, bom, max_x, max_y)

    # Warnings
    if warnings:
        _draw_warnings(ax, warnings, min_x, min_y)

    # Legend
    _draw_legend(ax, placed, cctv)

    # Title
    n_comp = len(placed)
    tw     = layout.get("total_wire_m", 0)
    title  = (f"PROJECT V1 — Electrical Layout\n"
              f"{len(rooms)} rooms · {n_comp} components · {tw}m wire")
    if cctv:
        title += f" · {len(cctv)} cameras · {layout.get('total_cat6_m',0)}m CAT6"

    _setup_ax(ax, title, min_x, max_x, min_y, max_y)

    plt.tight_layout()
    plt.savefig(output_path, dpi=160, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"[Renderer] Saved → {output_path}")
    return output_path


# ═════════════════════════════════════════════════════════════════════════════
#  ROOM DRAWING
# ═════════════════════════════════════════════════════════════════════════════
def _draw_room(ax, room):
    rx, ry = room["x"], room["y"]
    rw, rh = room["width"], room["height"]
    name   = room.get("name","unknown")
    fill   = ROOM_FILL.get(name, "#1C1C1C")

    # Room fill
    rect = mpatches.Rectangle(
        (rx, ry), rw, rh,
        linewidth=2.0, edgecolor=WHITE, facecolor=fill,
        alpha=0.85, zorder=1
    )
    ax.add_patch(rect)

    # Room label (type + dimensions)
    label = name.upper().replace("_"," ")
    dim   = f"{rw:.1f}×{rh:.1f}m"
    ax.text(rx+rw/2, ry+rh*0.65, label,
            color=WHITE, fontsize=6.5, ha="center", va="center",
            fontweight="bold", zorder=3,
            path_effects=[pe.withStroke(linewidth=1.5, foreground=DARK)])
    ax.text(rx+rw/2, ry+rh*0.42, dim,
            color=MUTED, fontsize=5.5, ha="center", va="center",
            zorder=3)

    # Doors
    for door in room.get("doors",[]):
        _draw_door(ax, room, door)

    # Windows
    for win in room.get("windows",[]):
        _draw_window(ax, room, win)


def _draw_door(ax, room, door):
    rx,ry = room["x"],room["y"]
    rw,rh = room["width"],room["height"]
    wall  = door.get("wall","bottom")
    pos   = door.get("position", rw/2)
    w     = door.get("width", 0.9)

    if wall=="bottom":
        dx,dy = rx+pos, ry
        # Gap in wall
        ax.plot([dx-w/2,dx+w/2],[dy,dy], color=DARK, lw=5, zorder=2)
        ax.add_patch(Arc((dx-w/2,dy), w, w, angle=0,
                         theta1=0, theta2=90,
                         color="#F39C12", lw=1.2, ls="--", zorder=4))
    elif wall=="top":
        dx,dy = rx+pos, ry+rh
        ax.plot([dx-w/2,dx+w/2],[dy,dy], color=DARK, lw=5, zorder=2)
        ax.add_patch(Arc((dx-w/2,dy), w, w, angle=0,
                         theta1=270, theta2=360,
                         color="#F39C12", lw=1.2, ls="--", zorder=4))
    elif wall=="left":
        dx,dy = rx, ry+pos
        ax.plot([dx,dx],[dy-w/2,dy+w/2], color=DARK, lw=5, zorder=2)
        ax.add_patch(Arc((dx,dy-w/2), w, w, angle=0,
                         theta1=0, theta2=90,
                         color="#F39C12", lw=1.2, ls="--", zorder=4))
    elif wall=="right":
        dx,dy = rx+rw, ry+pos
        ax.plot([dx,dx],[dy-w/2,dy+w/2], color=DARK, lw=5, zorder=2)
        ax.add_patch(Arc((dx,dy-w/2), w, w, angle=90,
                         theta1=90, theta2=180,
                         color="#F39C12", lw=1.2, ls="--", zorder=4))


def _draw_window(ax, room, win):
    rx,ry = room["x"],room["y"]
    rw,rh = room["width"],room["height"]
    wall  = win.get("wall","right")
    pos   = win.get("position", rh/2)
    w     = win.get("width",1.2)

    COLOR = "#1ABC9C"
    LW    = 3.5

    if wall=="right":
        ax.plot([rx+rw, rx+rw],
                [ry+pos-w/2, ry+pos+w/2], color=COLOR, lw=LW, zorder=3)
    elif wall=="left":
        ax.plot([rx, rx],
                [ry+pos-w/2, ry+pos+w/2], color=COLOR, lw=LW, zorder=3)
    elif wall=="top":
        ax.plot([rx+pos-w/2, rx+pos+w/2],
                [ry+rh, ry+rh],            color=COLOR, lw=LW, zorder=3)
    elif wall=="bottom":
        ax.plot([rx+pos-w/2, rx+pos+w/2],
                [ry, ry],                  color=COLOR, lw=LW, zorder=3)


# ═════════════════════════════════════════════════════════════════════════════
#  WIRE ROUTES
# ═════════════════════════════════════════════════════════════════════════════
def _draw_wire_routes(ax, routes, cctv_routes=None):
    for r in routes:
        sym   = r.get("symbol","default")
        color = WIRE_COLOR.get(sym, WIRE_COLOR["default"])
        wpts  = r["waypoints"]
        xs    = [p[0] for p in wpts]
        ys    = [p[1] for p in wpts]
        ax.plot(xs, ys, color=color, lw=0.9, ls="--",
                alpha=0.55, zorder=4)

    if cctv_routes:
        for cr in cctv_routes:
            wpts = cr["waypoints"]
            xs   = [p[0] for p in wpts]
            ys   = [p[1] for p in wpts]
            ax.plot(xs, ys, color="#E67E22", lw=1.1,
                    ls=":", alpha=0.65, zorder=4)
            # Length label at midpoint
            if len(wpts) >= 2:
                mi = len(wpts)//2
                mx = (wpts[mi-1][0]+wpts[mi][0])/2
                my = (wpts[mi-1][1]+wpts[mi][1])/2
                ax.text(mx, my, f"{cr['length_m']}m",
                        color="#E67E22", fontsize=5, zorder=7,
                        path_effects=[pe.withStroke(linewidth=1.5,
                                                    foreground=DARK)])


# ═════════════════════════════════════════════════════════════════════════════
#  BOM INSET
# ═════════════════════════════════════════════════════════════════════════════
def _draw_bom(ax, bom, max_x, max_y):
    lines = ["BILL OF MATERIALS", "─"*24]
    for item in bom:
        q  = item["qty"]
        u  = item.get("unit","pcs")
        nm = item["item"][:26]
        lines.append(f"{q:>5} {u:<7} {nm}")
    text = "\n".join(lines)

    ax.text(max_x + 0.4, max_y, text,
            color=WHITE, fontsize=5.8, va="top", ha="left",
            fontfamily="monospace", zorder=10,
            bbox=dict(boxstyle="round,pad=0.5", facecolor=PANEL,
                      edgecolor="#F1C40F", alpha=0.95))


# ═════════════════════════════════════════════════════════════════════════════
#  WARNINGS
# ═════════════════════════════════════════════════════════════════════════════
def _draw_warnings(ax, warnings, min_x, min_y):
    lines = ["⚠  VERIFY"] + [f"• {w[:55]}" for w in warnings[:5]]
    ax.text(min_x, min_y - 0.4, "\n".join(lines),
            color="#D29922", fontsize=5.8, va="top", ha="left",
            zorder=10,
            bbox=dict(boxstyle="round,pad=0.4", facecolor=PANEL,
                      edgecolor="#D29922", alpha=0.9))


# ═════════════════════════════════════════════════════════════════════════════
#  LEGEND
# ═════════════════════════════════════════════════════════════════════════════
def _draw_legend(ax, placed, cctv):
    # Count unique symbol types
    syms_present = list(dict.fromkeys(
        c["symbol"] for c in placed if c.get("symbol")
    ))[:10]

    els = [Line2D([0],[0], color=WIRE_COLOR.get(s,"#BDC3C7"),
                  lw=1.5, ls="--",
                  label=s.capitalize())
           for s in syms_present]

    if cctv:
        els.append(Line2D([0],[0], color="#E67E22", lw=1.5,
                          ls=":", label="CAT6 cable"))

    ax.legend(handles=els, loc="lower left", fontsize=5.5,
              facecolor=PANEL, edgecolor=BORDER,
              labelcolor=WHITE, framealpha=0.92,
              ncol=2, handlelength=1.5)


# ═════════════════════════════════════════════════════════════════════════════
#  AXIS SETUP
# ═════════════════════════════════════════════════════════════════════════════
def _setup_ax(ax, title, min_x, max_x, min_y, max_y):
    PAD  = 1.5
    ax.set_xlim(min_x - PAD, max_x + 8.5)   # extra right margin for BOM
    ax.set_ylim(min_y - 1.8, max_y + 1.0)
    ax.set_aspect("equal")
    ax.set_title(title, color=WHITE, fontsize=10, pad=8)
    ax.tick_params(colors=MUTED, labelsize=7)
    ax.set_xlabel("metres", color=MUTED, fontsize=8)
    ax.set_ylabel("metres", color=MUTED, fontsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor(BORDER)


def _draw_grid(ax, min_x, max_x, min_y, max_y):
    for x in np.arange(min_x, max_x+1, 1):
        ax.axvline(x, color=WHITE, lw=0.18, alpha=0.15)
    for y in np.arange(min_y, max_y+1, 1):
        ax.axhline(y, color=WHITE, lw=0.18, alpha=0.15)


def _sym_size(W, H):
    """Scale symbol size relative to plan size."""
    avg = (W + H) / 2
    return max(0.15, min(0.35, avg * 0.025))
