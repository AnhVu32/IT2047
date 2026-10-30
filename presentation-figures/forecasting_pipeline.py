import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

fig, ax = plt.subplots(figsize=(16, 6), facecolor='white')
ax.set_xlim(0, 16); ax.set_ylim(0, 6); ax.axis('off')
ax.text(.45, 5.45, 'Preparing data for price prediction', fontsize=25, weight='bold', color='#172b3a')
ax.text(.45, 5.02, 'Raw listings  →  model-ready dataset', fontsize=13, color='#617483')
steps = [
 ('01', 'Select & normalize', 'Keep useful fields\nStandardize property type\nand legal status', '#167d8d'),
 ('02', 'Clean records', 'Remove duplicate IDs\nCheck coordinates\nRemove missing bedrooms', '#3277a8'),
 ('03', 'Remove outliers', 'Apply property-specific\nlimits for area, bedrooms,\nprice and unit price', '#7667a8'),
 ('04', 'Encode for modeling', 'Create area per bedroom\nTransform price to log scale\nOne-hot encode categories', '#c17d42'),
]
for i, (num, title, body, color) in enumerate(steps):
    x = .45 + i * 3.94
    ax.add_patch(FancyBboxPatch((x, 1.38), 3.42, 2.95, boxstyle='round,pad=0.02,rounding_size=0.12', facecolor='#f7f9fa', edgecolor='#dbe4e8', linewidth=1.2))
    ax.text(x+.22, 3.84, num, fontsize=15, weight='bold', color=color)
    ax.text(x+.22, 3.32, title, fontsize=15, weight='bold', color='#172b3a')
    ax.text(x+.22, 2.88, body, fontsize=12, linespacing=1.65, va='top', color='#465d6b')
    if i < 3:
        ax.annotate('', xy=(x+3.88, 2.85), xytext=(x+3.48, 2.85), arrowprops=dict(arrowstyle='->', color='#97aab3', lw=2))
ax.text(.45, .65, 'Forecasting data pipeline', fontsize=11, color='#83939c')
fig.savefig('presentation-figures/forecasting-data-pipeline.png', dpi=200, bbox_inches='tight', facecolor='white')
fig.savefig('presentation-figures/forecasting-data-pipeline.svg', bbox_inches='tight', facecolor='white')
