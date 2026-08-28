import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
# import numpy as np
import pandas as pd
import seaborn as sns


data_lc = {
    'Config': [
        'Spacy / Vector Context Linker', 'Spacy / Faster Linker', 'Spacy / Embedding Linker',
        'Regex / Vector Context Linker', 'Regex / Faster Linker', 'Regex / Embedding Linker',],
    'Runtime': [68.16, 51.64, 321.37, 30.54, 6.21, 348.79],
    'F1': [0.6072, 0.5804, 0.5932, 0.5693, 0.5681, 0.5852]
}
data_cometa = {
    'Config': [
        'Spacy / Vector Context Linker', 'Spacy / Faster Linker', 'Spacy / Embedding Linker',
        'Regex / Vector Context Linker', 'Regex / Faster Linker', 'Regex / Embedding Linker',],
    'Runtime': [75.40, 48.05, 511.19, 117.55, 82.61, 248.02],
    'F1': [0.4112, 0.3871, 0.4215, 0.3722, 0.3664, 0.3847]
}


def draw(is_lc: bool):
# 1. Set style for high-visibility poster presentation
    sns.set_theme(style="whitegrid")
    plt.rcParams.update({
        'font.size': 14,
        'axes.labelsize': 16,
        'axes.titlesize': 18,
        'xtick.labelsize': 14,
        'ytick.labelsize': 14,
        'legend.fontsize': 10,
        'figure.titlesize': 20
    })
    if is_lc:
        data = data_lc
    else:
        data = data_cometa
    df = pd.DataFrame(data)

    # Sort by runtime to properly compute the trade-off frontier
    df = df.sort_values(by='Runtime').reset_index(drop=True)

    # Identify different types
    to_marker_map = {
        "Spacy": "*",
        "Regex": 'o',
    }
    df['marker'] = ''
    for part, marker in to_marker_map.items():
        df.loc[df['Config'].str.contains(part), 'marker'] = marker
    to_colour_map = {
        "Vector Context Linker": "blue",
        "Faster Linker": "red",
        "Embedding Linker": "green",
    }
    df['colour'] = ''
    for part, colour in to_colour_map.items():
        df.loc[df['Config'].str.contains(part), 'colour'] = colour

    fig, ax = plt.subplots(figsize=(7, 4))

    for marker_type in set(to_marker_map.values()):
        for cur_colour in set(to_colour_map.values()):
            cur_df = df[(df['colour'] == cur_colour) & (df['marker'] == marker_type)]
            ax.scatter(cur_df['Runtime'], cur_df['F1'], 
                    marker=marker_type,
                    color=cur_colour, s=120, alpha=0.6,
                    edgecolor='k', zorder=3)

    for i, row in df.iterrows():
        # Subtle offsets to prevent text overlaying directly on top of the dots
        xytext = (12, -5)
        if is_lc:
            if "Regex" in row['Config'] and "Faster Linker" in row['Config']:
                xytext = (12, -15)
        if "Embedding" in row['Config']:
            xytext = (-150, -5)
            if "Regex" in row['Config']:
                xytext = (-140, -15)

        ax.annotate(
            row['Config'],
            xy=(row['Runtime'], row['F1']),
            xytext=xytext,
            textcoords='offset points',
            fontsize=12,
            color='black',
        )

    # 6. Formatting Axis and Labels
    ax.set_xlabel('Runtime (seconds)', labelpad=10, weight='bold')
    ax.set_ylabel('$F_1$ Score', labelpad=10, weight='bold')
    ax.set_title(
        f'Speed vs performance for {"Linking Challenge" if is_lc else "COMETA"}',
        pad=15, weight='bold')

    # Adjust limits appropriately to give padding for text labels
    ax.set_ylim(df['F1'].min() - 0.005, df['F1'].max() + 0.005)
    ax.set_xlim(0, df['Runtime'].max() + 50)

    # Build custom handles for the Marker legend
    marker_handles = [
        Line2D([0], [0], marker=m, color='gray', linestyle='None', markersize=10, label=label)
        for label, m in to_marker_map.items()
    ]

    # Build custom handles for the Color legend
    # (We use a generic square 's' or circle 'o' marker just to showcase the color)
    color_handles = [
        Line2D([0], [0], marker='s', color='None', markerfacecolor=c, markeredgecolor=c, markersize=10, label=label)
        for label, c in to_colour_map.items()
    ]

    # Create and add the legends to the axis
    # First legend (Markers) - placed normally
    if is_lc:
        leg1 = ax.legend(handles=marker_handles, title="Shape Meaning", loc='upper right', frameon=True)
    else:
        leg1 = ax.legend(handles=marker_handles, title="Shape Meaning", loc='center right', frameon=True)

    # Second legend (Colors) - added manually so it doesn't overwrite the first one
    leg2 = ax.legend(handles=color_handles, title="Color Meaning", loc='lower right', frameon=True)
    ax.add_artist(leg1) # CRITICAL: This prevents leg2 from deleting leg1


    plt.tight_layout()
    if is_lc:
        plt.savefig('tradeoff_lc.png', dpi=300, transparent=True)
    else:
        plt.savefig('tradeoff_cometa.png', dpi=300, transparent=True)


if __name__ == "__main__":
    from sys import argv
    if len(argv) < 2:
        print("Assuming linking challenge")
        is_lc = True
    else:
        is_lc = (
            "lc" in argv[1].lower() or
            "linking" in argv[1].lower() or
            "challenge" in argv[1].lower())
    print("Doing dataset", "Linking Challenge" if is_lc else "COMETA")
    draw(is_lc)
