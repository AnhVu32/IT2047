from pathlib import Path
import importlib.util
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
root=Path(__file__).resolve().parents[1]; base=root/'Data/forecasting-data'
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
s1=load('s1',base/'step-1/remove-unreliable-features.py'); s2=load('s2',base/'step-2/data-cleanup.py'); s3=load('s3',base/'step-3/data-finalize.py')
raw=pd.read_csv(s1.INPUT_FILE,dtype={'listing_id':'string'},low_memory=False)
a=s2.remove_furnishing(s2.bedrooms_filter(s2.coordinates_filter(s2.duplicate_records_filter(s1.build_reliable_dataset(raw)))))
b,apt,house=s3.remove_outliers(a)
fig,ax=plt.subplots(figsize=(16,7),facecolor='white'); ax.set_xlim(0,16); ax.set_ylim(0,7); ax.axis('off')
ax.text(.55,6.45,'Step 3: Remove outliers',fontsize=25,weight='bold',color='#172b3a')
ax.text(.55,6.03,'Apply separate residential limits for apartments and houses / land',fontsize=13,color='#617483')
for x,label,title,color in [(.55,'BEFORE','Cleaned records','#3277a8'),(8.65,'AFTER','Within model limits','#167d8d')]:
 ax.add_patch(FancyBboxPatch((x,1.1),6.8,4.4,boxstyle='round,pad=0.02,rounding_size=0.12',facecolor='#f7f9fa',edgecolor='#dbe4e8'))
 ax.text(x+.3,5.1,label,fontsize=13,weight='bold',color=color); ax.text(x+.3,4.65,title,fontsize=18,weight='bold',color='#172b3a')
ax.text(.85,4.05,f'{len(a):,} records',fontsize=16,weight='bold',color='#344e5c')
ax.text(.85,3.55,'Some listings fall outside the limits for\narea, bedrooms, asking price or unit price.',fontsize=13,linespacing=1.65,color='#465d6b',va='top')
ax.text(8.95,4.05,f'{len(b):,} records',fontsize=16,weight='bold',color='#344e5c')
ax.text(8.95,3.55,f'{apt:,} apartment outliers removed\n{house:,} house / land outliers removed',fontsize=13,linespacing=1.65,color='#465d6b',va='top')
ax.text(8.95,2.38,'Apartments: 25–150 m²; 1–4 bedrooms\nHouses / land: 20–350 m²; 1–8 bedrooms',fontsize=12,linespacing=1.65,color='#465d6b',va='top')
ax.annotate('',xy=(8.42,3.25),xytext=(7.55,3.25),arrowprops=dict(arrowstyle='->',color='#97aab3',lw=2.5))
ax.text(.55,.5,'Price and price-per-m² limits also apply; counts are calculated using the current pipeline rules.',fontsize=11,color='#718691')
fig.savefig(root/'presentation-figures/forecasting-step3-before-after.png',dpi=200,bbox_inches='tight',facecolor='white')
fig.savefig(root/'presentation-figures/forecasting-step3-before-after.svg',bbox_inches='tight',facecolor='white')
