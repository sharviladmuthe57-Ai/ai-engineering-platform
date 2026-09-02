"""
symbols.py — SVG-style electrical symbol library for matplotlib
================================================================
Each draw_* function takes (ax, x, y, size, color) and renders the
standard electrical symbol at that world coordinate.
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
from matplotlib.patches import Arc, FancyArrow, Circle, Rectangle, Wedge
from matplotlib.lines   import Line2D

DARK = "#0D1117"
# Symbol size in axes units (metres)
SZ   = 0.28


# ── HELPER: stroke effect ─────────────────────────────────────────────────
def stroke(color="#0D1117", lw=2.0):
    return [pe.withStroke(linewidth=lw, foreground=color)]


# ── INDIVIDUAL SYMBOL DRAWERS ─────────────────────────────────────────────

def draw_light(ax, x, y, sz=SZ, color="#F1C40F", zorder=8):
    """Ceiling light: circle with cross inside."""
    c = Circle((x,y), sz*0.9, fill=True, facecolor=color, edgecolor=DARK,
               linewidth=1.0, zorder=zorder)
    ax.add_patch(c)
    for ang in [0, 90]:
        rad = np.radians(ang)
        ax.plot([x - sz*0.75*np.cos(rad), x + sz*0.75*np.cos(rad)],
                [y - sz*0.75*np.sin(rad), y + sz*0.75*np.sin(rad)],
                color=DARK, lw=1.2, zorder=zorder+1)
    ax.text(x, y - sz*1.4, "L", color=color, fontsize=5.5, ha="center",
            zorder=zorder+1, path_effects=stroke())


def draw_fan(ax, x, y, sz=SZ, color="#1ABC9C", zorder=8):
    """Ceiling fan: circle with 3 blade arcs."""
    c = Circle((x,y), sz*0.75, fill=False, edgecolor=color, lw=1.2, zorder=zorder)
    ax.add_patch(c)
    for ang in [0, 120, 240]:
        rad = np.radians(ang)
        ax.add_patch(Arc((x + sz*0.5*np.cos(rad), y + sz*0.5*np.sin(rad)),
                         sz*0.7, sz*0.3,
                         angle=ang, theta1=0, theta2=180,
                         color=color, lw=1.2, zorder=zorder))
    ax.text(x, y - sz*1.4, "FAN", color=color, fontsize=4.5, ha="center",
            zorder=zorder+1, path_effects=stroke())


def draw_exhaust(ax, x, y, sz=SZ, color="#2ECC71", zorder=8):
    """Exhaust fan: square with arrow."""
    r = Rectangle((x-sz, y-sz), sz*2, sz*2,
                  fill=False, edgecolor=color, lw=1.2, zorder=zorder)
    ax.add_patch(r)
    ax.annotate("", xy=(x, y+sz*0.5), xytext=(x, y-sz*0.5),
                arrowprops=dict(arrowstyle="->", color=color, lw=1.2),
                zorder=zorder+1)
    ax.text(x, y - sz*1.55, "EXH", color=color, fontsize=4.5, ha="center",
            zorder=zorder+1, path_effects=stroke())


def draw_switch(ax, x, y, sz=SZ, color="#3498DB", zorder=8):
    """Switch: rectangle with line and arc."""
    r = Rectangle((x-sz*0.8, y-sz*0.5), sz*1.6, sz*1.0,
                  fill=True, facecolor="#1A2530", edgecolor=color,
                  lw=1.2, zorder=zorder)
    ax.add_patch(r)
    ax.plot([x-sz*0.4, x+sz*0.4], [y, y], color=color, lw=1.5, zorder=zorder+1)
    ax.plot([x+sz*0.4, x+sz*0.7], [y, y+sz*0.45],
            color=color, lw=1.5, zorder=zorder+1)
    ax.text(x, y - sz*1.1, "SW", color=color, fontsize=4.5, ha="center",
            zorder=zorder+1, path_effects=stroke())


def draw_switch2(ax, x, y, sz=SZ, color="#5DADE2", zorder=8):
    """2-Way switch: two lines."""
    r = Rectangle((x-sz*0.8, y-sz*0.5), sz*1.6, sz*1.0,
                  fill=True, facecolor="#1A2530", edgecolor=color,
                  lw=1.2, zorder=zorder)
    ax.add_patch(r)
    ax.plot([x-sz*0.4, x+sz*0.7], [y+sz*0.2, y+sz*0.5], color=color, lw=1.2, zorder=zorder+1)
    ax.plot([x-sz*0.4, x+sz*0.7], [y-sz*0.2, y-sz*0.5], color=color, lw=1.2, zorder=zorder+1)
    ax.text(x, y - sz*1.1, "2W", color=color, fontsize=4.5, ha="center",
            zorder=zorder+1, path_effects=stroke())


def draw_outlet(ax, x, y, sz=SZ, color="#E74C3C", zorder=8):
    """5-pin socket: rectangle with 3 dots."""
    r = Rectangle((x-sz, y-sz*0.7), sz*2, sz*1.4,
                  fill=True, facecolor="#1A1A1A", edgecolor=color,
                  lw=1.2, zorder=zorder)
    ax.add_patch(r)
    # Top pin (earth)
    ax.plot(x, y+sz*0.25, "o", ms=3.5, color=color, zorder=zorder+1)
    # Two lower pins
    ax.plot(x-sz*0.35, y-sz*0.2, "o", ms=3.5, color=color, zorder=zorder+1)
    ax.plot(x+sz*0.35, y-sz*0.2, "o", ms=3.5, color=color, zorder=zorder+1)
    ax.text(x, y - sz*1.2, "SOC", color=color, fontsize=4.5, ha="center",
            zorder=zorder+1, path_effects=stroke())


def draw_outlet2(ax, x, y, sz=SZ, color="#EC7063", zorder=8):
    """2-pin socket: rectangle with 2 dots."""
    r = Rectangle((x-sz*0.8, y-sz*0.7), sz*1.6, sz*1.4,
                  fill=True, facecolor="#1A1A1A", edgecolor=color,
                  lw=1.2, zorder=zorder)
    ax.add_patch(r)
    ax.plot(x-sz*0.25, y, "o", ms=3.5, color=color, zorder=zorder+1)
    ax.plot(x+sz*0.25, y, "o", ms=3.5, color=color, zorder=zorder+1)
    ax.text(x, y - sz*1.2, "2P", color=color, fontsize=4.5, ha="center",
            zorder=zorder+1, path_effects=stroke())


def draw_ac(ax, x, y, sz=SZ, color="#9B59B6", zorder=8):
    """AC point: rectangle with wave."""
    r = Rectangle((x-sz*1.0, y-sz*0.6), sz*2.0, sz*1.2,
                  fill=True, facecolor="#1A1A1A", edgecolor=color,
                  lw=1.2, zorder=zorder)
    ax.add_patch(r)
    xs = np.linspace(x-sz*0.7, x+sz*0.7, 30)
    ys = y + sz*0.15*np.sin(np.linspace(0, 2*np.pi*2, 30))
    ax.plot(xs, ys, color=color, lw=1.2, zorder=zorder+1)
    ax.text(x, y - sz*1.1, "AC", color=color, fontsize=5, ha="center",
            fontweight="bold", zorder=zorder+1, path_effects=stroke())


def draw_geyser(ax, x, y, sz=SZ, color="#E67E22", zorder=8):
    """Geyser: circle with water drop."""
    c = Circle((x,y), sz*0.85, fill=True, facecolor="#1A1A1A",
               edgecolor=color, lw=1.2, zorder=zorder)
    ax.add_patch(c)
    # Water drop
    ax.plot(x, y+sz*0.4, "v", ms=6, color=color, zorder=zorder+1)
    ax.text(x, y - sz*1.4, "GEY", color=color, fontsize=4.5, ha="center",
            zorder=zorder+1, path_effects=stroke())


def draw_tv(ax, x, y, sz=SZ, color="#8E44AD", zorder=8):
    """TV point: rectangle with TV label."""
    r = Rectangle((x-sz, y-sz*0.7), sz*2, sz*1.4,
                  fill=True, facecolor="#1A1A1A", edgecolor=color,
                  lw=1.2, zorder=zorder)
    ax.add_patch(r)
    ax.text(x, y+sz*0.1, "TV", color=color, fontsize=6.5, ha="center",
            va="center", fontweight="bold", zorder=zorder+1)
    ax.text(x, y - sz*1.2, "TV", color=color, fontsize=4.5, ha="center",
            zorder=zorder+1, path_effects=stroke())


def draw_wifi(ax, x, y, sz=SZ, color="#2980B9", zorder=8):
    """WiFi: three arc waves."""
    for i, (r, a1, a2) in enumerate([(sz*0.4,45,135),(sz*0.65,50,130),(sz*0.9,55,125)]):
        ax.add_patch(Arc((x, y-sz*0.2), r*2, r*2, angle=0,
                         theta1=a1, theta2=a2,
                         color=color, lw=1.0+i*0.3, zorder=zorder))
    ax.plot(x, y-sz*0.2, "o", ms=3, color=color, zorder=zorder+1)
    ax.text(x, y - sz*1.4, "WiFi", color=color, fontsize=4.5, ha="center",
            zorder=zorder+1, path_effects=stroke())


def draw_bell(ax, x, y, sz=SZ, color="#F39C12", zorder=8):
    """Door bell: bell shape."""
    c = Circle((x,y), sz*0.8, fill=True, facecolor="#1A1A1A",
               edgecolor=color, lw=1.2, zorder=zorder)
    ax.add_patch(c)
    ax.text(x, y, "DB", color=color, fontsize=5.5, ha="center", va="center",
            fontweight="bold", zorder=zorder+1)
    ax.text(x, y - sz*1.4, "BELL", color=color, fontsize=4.5, ha="center",
            zorder=zorder+1, path_effects=stroke())


def draw_smoke(ax, x, y, sz=SZ, color="#BDC3C7", zorder=8):
    """Smoke detector: circle with S."""
    c = Circle((x,y), sz*0.8, fill=True, facecolor="#2C3E50",
               edgecolor=color, lw=1.2, zorder=zorder)
    ax.add_patch(c)
    ax.text(x, y, "S", color=color, fontsize=7, ha="center", va="center",
            fontweight="bold", zorder=zorder+1)
    ax.text(x, y - sz*1.4, "SMOK", color=color, fontsize=4.5, ha="center",
            zorder=zorder+1, path_effects=stroke())


def draw_mcb(ax, x, y, sz=SZ, color="#F1C40F", zorder=8):
    """MCB: small rectangle with lightning bolt."""
    r = Rectangle((x-sz*0.6, y-sz*0.9), sz*1.2, sz*1.8,
                  fill=True, facecolor="#1A1A1A", edgecolor=color,
                  lw=1.5, zorder=zorder)
    ax.add_patch(r)
    ax.text(x, y, "⚡", fontsize=7, ha="center", va="center", zorder=zorder+1)
    ax.text(x, y - sz*1.5, "MCB", color=color, fontsize=4.5, ha="center",
            zorder=zorder+1, path_effects=stroke())


def draw_db(ax, x, y, sz=SZ, color="#E74C3C", zorder=8):
    """Distribution board: large rectangle with grid."""
    rw, rh = sz*2.5, sz*3.0
    r = Rectangle((x-rw/2, y-rh/2), rw, rh,
                  fill=True, facecolor="#1A1A1A", edgecolor=color,
                  lw=2.0, zorder=zorder)
    ax.add_patch(r)
    for row in range(4):
        ry_ = y - rh/2 + rh/(4+1) * (row+1)
        ax.plot([x-rw*0.35, x+rw*0.35], [ry_,ry_],
                color=color, lw=0.8, alpha=0.6, zorder=zorder+1)
    ax.text(x, y, "DB", color=color, fontsize=7, ha="center", va="center",
            fontweight="bold", zorder=zorder+1)
    ax.text(x, y - rh/2 - sz*0.5, "DIST BOARD",
            color=color, fontsize=4.5, ha="center",
            zorder=zorder+1, path_effects=stroke())


def draw_emlight(ax, x, y, sz=SZ, color="#E74C3C", zorder=8):
    """Emergency light: rectangle with E."""
    r = Rectangle((x-sz, y-sz*0.5), sz*2, sz*1.0,
                  fill=True, facecolor="#1A1A1A", edgecolor=color,
                  lw=1.2, zorder=zorder)
    ax.add_patch(r)
    ax.text(x, y, "EM", color=color, fontsize=6, ha="center", va="center",
            fontweight="bold", zorder=zorder+1)
    ax.text(x, y - sz*1.1, "EMRG", color=color, fontsize=4.5, ha="center",
            zorder=zorder+1, path_effects=stroke())


def draw_cctv(ax, x, y, sz=SZ, color="#E67E22", zorder=8):
    """CCTV camera: circle with lens wedge."""
    c = Circle((x,y), sz*0.9, fill=True, facecolor="#1A1A1A",
               edgecolor=color, lw=1.5, zorder=zorder)
    ax.add_patch(c)
    w = Wedge((x,y), sz*0.6, -20, 20, fill=True,
              facecolor=color, edgecolor=color, lw=0, zorder=zorder+1)
    ax.add_patch(w)
    ax.text(x, y - sz*1.4, "CAM", color=color, fontsize=4.5, ha="center",
            zorder=zorder+1, path_effects=stroke())


# ── DISPATCH TABLE ───────────────────────────────────────────────────────────
DRAW_FN = {
    "light"   : draw_light,
    "fan"     : draw_fan,
    "exhaust" : draw_exhaust,
    "switch"  : draw_switch,
    "switch2" : draw_switch2,
    "outlet"  : draw_outlet,
    "outlet2" : draw_outlet2,
    "ac"      : draw_ac,
    "geyser"  : draw_geyser,
    "tv"      : draw_tv,
    "wifi"    : draw_wifi,
    "bell"    : draw_bell,
    "smoke"   : draw_smoke,
    "mcb"     : draw_mcb,
    "db"      : draw_db,
    "emlight" : draw_emlight,
    "camera"  : draw_cctv,
}

SYMBOL_COLORS = {
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
    "bell"   : "#F39C12",
    "smoke"  : "#BDC3C7",
    "mcb"    : "#F1C40F",
    "db"     : "#E74C3C",
    "emlight": "#E74C3C",
    "camera" : "#E67E22",
}


def draw_symbol(ax, symbol_id: str, x: float, y: float,
                sz: float = SZ, zorder: int = 8):
    """Main entry point. Draw any symbol by its ID."""
    fn    = DRAW_FN.get(symbol_id, draw_outlet)
    color = SYMBOL_COLORS.get(symbol_id, "#BDC3C7")
    fn(ax, x, y, sz=sz, color=color, zorder=zorder)
    return color

