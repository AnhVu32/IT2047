from pathlib import Path
import importlib.util
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
root=Path(__file__).resolve().parents[1]; base=root/'Data/forecasting-data'
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
s1=load('s1',base/'step-1/remove-unreliable-features.py'); s2=load('s2',base/'step-2/data-cleanup.py'); s3=load('s3',base/'step-3/data-finalize.py')
raw=pd.read_csv(s1.INPUT_FILE,dtype={'listing_id':'string'},low_memory=False)
before=s2.remove_furnishing(s2.bedrooms_filter(s2.coordinates_filter(s2.duplicate_records_filter(s1.build_reliable_dataset(raw)))))
after,_,_=s3.remove_outliers(before)
for df in (before,after): df['unit_price']=df['price_range']*1000/df['area']
# Fixed ranges make the two panels comparable; values outside the windows are counted explicitly.
plots=[('area','Area (m²)',0,400),('bedrooms','Bedrooms',0,10),('price_range','Asking price (billion VND)',0,50),('unit_price','Unit price (million VND/m²)',0,400)]
ylimits = {}
for col, _, lo, hi in plots:
 vals = pd.to_numeric(before[col], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
 counts, _ = np.histogram(vals, bins=np.linspace(lo, hi, 26))
 ylimits[col] = max(counts.max() * 1.15, 1)
colors={'Căn hộ':'#3277a8','Nhà đất':'#c17d42'}
for name,df in [('before',before),('after',after)]:
 fig,axes=plt.subplots(2,2,figsize=(14,9),facecolor='white')
 fig.suptitle(f'Step 3: Distributions {name} outlier filtering',fontsize=22,weight='bold',color='#172b3a',x=.07,ha='left')
 fig.text(.07,.925,f'{len(df):,} records  •  Same display ranges in both figures',fontsize=12,color='#617483')
 for ax,(col,label,lo,hi) in zip(axes.flat,plots):
  vals=pd.to_numeric(df[col],errors='coerce'); shown=df[vals.between(lo,hi)].copy()
  sns.histplot(data=shown,x=col,hue='property_type',hue_order=['Căn hộ','Nhà đất'],palette=colors,bins=np.linspace(lo,hi,26),multiple='stack',ax=ax)
  ax.set_xlim(lo,hi); ax.set_ylim(0, ylimits[col]); ax.set_title(label,loc='left',fontsize=14,weight='bold',color='#172b3a'); ax.set_xlabel(label); ax.set_ylabel('Listings')
  ax.text(.98,.96,f'Outside range / missing: {len(df)-len(shown):,}',transform=ax.transAxes,ha='right',va='top',fontsize=9,color='#617483')
  ax.spines[['top','right']].set_visible(False)
 fig.tight_layout(rect=[0,0,1,.9],h_pad=2,w_pad=2)
 fig.savefig(root/f'presentation-figures/forecasting-step3-distributions-{name}.png',dpi=180,bbox_inches='tight',facecolor='white')
 fig.savefig(root/f'presentation-figures/forecasting-step3-distributions-{name}.svg',bbox_inches='tight',facecolor='white')
 plt.close(fig)
