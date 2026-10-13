"""Style commun des graphiques du projet : sobre, lisible, couleurs fixes."""
import matplotlib.pyplot as plt

# Palette catégorielle, toujours dans cet ordre (jamais réordonnée selon le graphique).
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
BLUE_RAMP = "Blues"          # une seule teinte, du clair au foncé, pour les intensités
INK = "#0b0b0b"              # texte principal
INK_2 = "#52514e"            # texte secondaire, axes
GRID = "#e4e3df"             # grille discrète
SURFACE = "#fcfcfb"
NEUTRAL = "#b9b8b3"          # pour ce qui n'est pas le sujet du graphique

# Couleur fixe par famille de cause de fin : la même dans tous les notebooks.
FAMILY_COLORS = {
    "Fin normale": NEUTRAL,
    "Défaut véhicule": PALETTE[1],
    "Défaut matériel": PALETTE[0],
    "Ambiguë (exclue)": PALETTE[3],
}


def set_style() -> None:
    plt.rcParams.update({
        "figure.figsize": (10, 4),
        "figure.dpi": 110,
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "axes.edgecolor": GRID,
        "axes.labelcolor": INK_2,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.titlecolor": INK,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "axes.prop_cycle": plt.cycler(color=PALETTE),
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "xtick.color": INK_2,
        "ytick.color": INK_2,
        "lines.linewidth": 2,
        "legend.frameon": False,
        "font.size": 10,
    })
