from pathlib import Path
import importlib.util
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('step1', root / 'Data/forecasting-data/step-1/remove-unreliable-features.py')
step = importlib.util.module_from_spec(spec); spec.loader.exec_module(step)
raw = pd.read_csv(step.INPUT_FILE, dtype={'listing_id':'string'}, low_memory=False)
before = raw.loc[raw['listing_id'] == '24712656'].iloc[[0]]
after = step.build_reliable_dataset(before)
fields = ['listing_id','property_type','area','latitude','longitude','district','bedrooms','legal_status','furnishing','price_range']
def fmt(v):
    if pd.isna(v): return 'Missing'
    if isinstance(v, float): return f'{v:g}'
    return str(v)
fig, ax = plt.subplots(figsize=(16,8), facecolor='white'); ax.set_xlim(0,16); ax.set_ylim(0,8); ax.axis('off')
ax.text(.55,7.4,'Step 1: A real listing before and after',fontsize=24,weight='bold',color='#172b3a')
ax.text(.55,6.98,'Selected fields from the same raw record  •  price in billion VND, area in m²',fontsize=12.5,color='#617483')
for x,label,sub,color in [(.55,'BEFORE','Raw record','#3277a8'),(8.6,'AFTER','Step 1 output','#167d8d')]:
    ax.add_patch(FancyBboxPatch((x,.9),6.85,5.7,boxstyle='round,pad=0.02,rounding_size=0.12',facecolor='#f7f9fa',edgecolor='#dbe4e8'))
    ax.text(x+.3,6.24,label,fontsize=12,weight='bold',color=color)
    ax.text(x+.3,5.85,sub,fontsize=17,weight='bold',color='#172b3a')
    row = before.iloc[0] if label == 'BEFORE' else after.iloc[0]
    for i,field in enumerate(fields):
        y=5.42-i*.405
        ax.text(x+.3,y,field,fontsize=11.5,color='#617483',va='center')
        ax.text(x+2.5,y,fmt(row[field]),fontsize=11.5,weight='bold' if field in ('property_type','legal_status') else 'normal',color=color if field in ('property_type','legal_status') else '#172b3a',va='center')
ax.annotate('',xy=(8.35,3.8),xytext=(7.65,3.8),arrowprops=dict(arrowstyle='->',color='#97aab3',lw=2.5))
ax.text(.55,.4,'Other raw columns are omitted here. Step 1 keeps all records; furnishing is removed in Step 2.',fontsize=11,color='#718691')
fig.savefig(root/'presentation-figures/forecasting-step1-real-example.png',dpi=200,bbox_inches='tight',facecolor='white')
fig.savefig(root/'presentation-figures/forecasting-step1-real-example.svg',bbox_inches='tight',facecolor='white')
