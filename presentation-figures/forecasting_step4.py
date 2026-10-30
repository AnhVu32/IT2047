from pathlib import Path
import importlib.util
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
root=Path(__file__).resolve().parents[1]; base=root/'Data/forecasting-data'
spec=importlib.util.spec_from_file_location('step4',base/'step-4/data-encoding.py'); step=importlib.util.module_from_spec(spec); spec.loader.exec_module(step)
before=pd.read_excel(step.INPUT_FILE,dtype={'listing_id':'string'}); after=step.encode_categoricals(step.add_features(before))
fig,ax=plt.subplots(figsize=(16,7),facecolor='white'); ax.set_xlim(0,16); ax.set_ylim(0,7); ax.axis('off')
ax.text(.55,6.45,'Step 4: Encode for modeling',fontsize=25,weight='bold',color='#172b3a')
ax.text(.55,6.03,'Turn cleaned listings into numerical features and a transformed target',fontsize=13,color='#617483')
for x,label,title,color in [(.55,'BEFORE','Outliers removed','#3277a8'),(8.65,'AFTER','Model-ready data','#167d8d')]:
 ax.add_patch(FancyBboxPatch((x,1.1),6.8,4.4,boxstyle='round,pad=0.02,rounding_size=0.12',facecolor='#f7f9fa',edgecolor='#dbe4e8'))
 ax.text(x+.3,5.1,label,fontsize=13,weight='bold',color=color); ax.text(x+.3,4.65,title,fontsize=18,weight='bold',color='#172b3a')
ax.text(.85,4.05,f'{len(before):,} records  •  {len(before.columns)} columns',fontsize=16,weight='bold',color='#344e5c')
ax.text(.85,3.5,'Numeric property details and asking price\nCategorical property type, legal status\nand district / ward',fontsize=13,linespacing=1.7,color='#465d6b',va='top')
ax.text(8.95,4.05,f'{len(after):,} records  •  {len(after.columns)} columns',fontsize=16,weight='bold',color='#344e5c')
ax.text(8.95,3.5,'Area per bedroom added\nPrice transformed to log-price target\nCategories converted to one-hot columns\nListing ID retained for tracking',fontsize=13,linespacing=1.7,color='#465d6b',va='top')
ax.annotate('',xy=(8.42,3.25),xytext=(7.55,3.25),arrowprops=dict(arrowstyle='->',color='#97aab3',lw=2.5))
ax.text(.55,.5,'The model uses the encoded features; listing ID is excluded from training and log-price is the target.',fontsize=11,color='#718691')
fig.savefig(root/'presentation-figures/forecasting-step4-before-after.png',dpi=200,bbox_inches='tight',facecolor='white')
fig.savefig(root/'presentation-figures/forecasting-step4-before-after.svg',bbox_inches='tight',facecolor='white')
