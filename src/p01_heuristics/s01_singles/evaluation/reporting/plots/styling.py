import matplotlib.pyplot as plt
import seaborn as sns

# ---------------------------------------------------------------------------
# PAPER DESIGN TOKENS (Scientific Style)
# ---------------------------------------------------------------------------

COLORS = {
    "primary": "#1f77b4",      # Steel Blue
    "secondary": "#9467bd",    # Muted Purple
    "success": "#2ca02c",      # Forest Green
    "danger": "#d62728",       # Brick Red
    "warning": "#ff7f0e",      # Safety Orange
    "dark": "#1a1a1b",         # Near Black for text
    "light": "#fdfdfd",        # Off-white
    "gray": "#7f7f7f",         # Neutral Gray
    "background": "#ffffff",
    "grid": "#e1e1e1"
}

# Professional Colormaps
RD_YL_GN_PREMIUM = sns.diverging_palette(15, 135, s=70, l=55, n=256, as_cmap=True)
BLUES_PREMIUM = sns.cubehelix_palette(start=.5, rot=-.5, as_cmap=True)

# ---------------------------------------------------------------------------
# STYLE CONFIGURATION
# ---------------------------------------------------------------------------

def apply_premium_style():
    """Sets a global professional scientific style."""
    sns.set_theme(style="white", context="paper")
    
    plt.rcParams.update({
        # Layout & Spines (Paper thin & Clean)
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": 0.8,
        "axes.edgecolor": COLORS["dark"],
        
        # Grid (Very subtle)
        "axes.grid": True,
        "grid.color": COLORS["grid"],
        "grid.linestyle": ":",
        "grid.alpha": 0.6,
        "axes.axisbelow": True,
        
        # Typography (Modern & Formal)
        "font.family": "serif",
        "font.serif": ["Times New Roman", "DejaVu Serif", "serif"],
        "axes.titlesize": 16,
        "axes.titleweight": "bold",
        "axes.labelsize": 12,
        "axes.labelweight": "medium",
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 10,
        
        # Saving
        "savefig.dpi": 400,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.02,  # Minimize margins for paper integration
    })

def finalize_plot(fig, title=None, subtitle=None):
    """Clean export: No text labels. Chart area is maximized."""
    # Remove margins entirely for LaTeX/Word inclusion
    fig.tight_layout(pad=0.1)

def get_display_name(name: str) -> str:
    """Standardized display name formatter with text-based prefixes."""
    if not isinstance(name, str):
        return str(name)
        
    name_lower = name.lower()
    # poke-env baselines
    if name_lower in {"random", "max_power", "simple_heuristic"}:
        return f"(B) {name}"
    # heuristics (v1-v6)
    if name_lower.startswith("v") and len(name_lower) > 1 and name_lower[1:].isdigit():
        return f"(H) {name}"
    # Pokechamp agents
    if name_lower in {"abyssal", "one_step", "safe_one_step", "pokechamp", "pokellmon"}:
        return f"(C) {name}"
    return name

def get_category_color(name_with_prefix: str) -> str:
    """Returns a color based on the agent category prefix."""
    if not isinstance(name_with_prefix, str):
        return COLORS["dark"]
        
    if "(B)" in name_with_prefix:
        return COLORS["primary"]
    if "(H)" in name_with_prefix:
        return COLORS["success"]
    if "(C)" in name_with_prefix:
        return COLORS["secondary"]
    return COLORS["dark"]
