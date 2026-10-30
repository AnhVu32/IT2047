from pathlib import Path
import importlib.util
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
root=Path(__file__).resolve().parents[1]; base=root/'Data/forecasting-data'
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
s1=load('s1',base/'step-1/remove-unreliable-features.py'); s2=load('s2',base/'step-2/data-cleanup.py')
raw=pd.read_csv(s1.INPUT_FILE,dtype={'listing_id':'string'},low_memory=False); a=s1.build_reliable_dataset(raw)
b=s2.duplicate_records_filter(a); c=s2.coordinates_filter(b); d=s2.bedrooms_filter(c); e=s2.remove_furnishing(d)
fig,ax=plt.subplots(figsize=(16,7),facecolor='white'); ax.set_xlim(0,16); ax.set_ylim(0,7); ax.axis('off')
ax.text(.55,6.45,'Step 2: Clean records',fontsize=25,weight='bold',color='#172b3a')
ax.text(.55,6.03,'Sequential checks prepare the selected fields for outlier filtering',fontsize=13,color='#617483')
for x,label,title,color in [(.55,'BEFORE','Step 1 output','#3277a8'),(8.65,'AFTER','Cleaned records','#167d8d')]:
 ax.add_patch(FancyBboxPatch((x,1.15),6.8,4.35,boxstyle='round,pad=0.02,rounding_size=0.12',facecolor='#f7f9fa',edgecolor='#dbe4e8'))
 ax.text(x+.3,5.1,label,fontsize=13,weight='bold',color=color); ax.text(x+.3,4.65,title,fontsize=18,weight='bold',color='#172b3a')
ax.text(.85,4.0,f'{len(a):,} records  •  {len(a.columns)} columns',fontsize=16,weight='bold',color='#344e5c')
ax.text(.85,3.45,'May include duplicate IDs, coordinates outside\nthe validation box, and missing bedrooms.',fontsize=13,linespacing=1.7,color='#465d6b',va='top')
ax.text(.85,2.3,'Includes the furnishing field.',fontsize=13,color='#465d6b')
ax.text(8.95,4.0,f'{len(e):,} records  •  {len(e.columns)} columns',fontsize=16,weight='bold',color='#344e5c')
ax.text(8.95,3.55,f'{len(a)-len(b):,} duplicate records removed\n{len(b)-len(c):,} records removed for invalid coordinates\n{len(c)-len(d):,} records removed for missing bedrooms\nFurnishing column removed',fontsize=13,linespacing=1.75,color='#465d6b',va='top')
ax.annotate('',xy=(8.42,3.25),xytext=(7.55,3.25),arrowprops=dict(arrowstyle='->',color='#97aab3',lw=2.5))
ax.text(.55,.53,'Counts are computed sequentially from the current source. The coordinate box is a coarse geographic check.',fontsize=11,color='#718691')
fig.savefig(root/'presentation-figures/forecasting-step2-before-after.png',dpi=200,bbox_inches='tight',facecolor='white')
fig.savefig(root/'presentation-figures/forecasting-step2-before-after.svg',bbox_inches='tight',facecolor='white')
