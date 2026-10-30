from pathlib import Path
import sys
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
root=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(root/'backend'))
from src.services.inference.price_prediction import PricePredictionService
listing=pd.read_excel(root/'Data/forecasting-data/step-3/outliers_removed.xlsx',dtype={'listing_id':'string'}).set_index('listing_id').loc['24712656']
result=PricePredictionService().predict(property_type=listing.property_type,area=listing.area,bedrooms=listing.bedrooms,latitude=listing.latitude,longitude=listing.longitude,district=listing.district,legal_status=listing.legal_status)
fig,ax=plt.subplots(figsize=(16,7),facecolor='white'); ax.set_xlim(0,16); ax.set_ylim(0,7); ax.axis('off')
ax.text(.55,6.45,'Price prediction: a real example',fontsize=25,weight='bold',color='#172b3a')
ax.text(.55,6.03,'Listing 24712656  •  Inputs supplied to the deployed model service',fontsize=13,color='#617483')
for x,label,title,color in [(.55,'INPUT','Property attributes','#3277a8'),(8.65,'OUTPUT','Price estimate','#167d8d')]:
 ax.add_patch(FancyBboxPatch((x,1.1),6.8,4.4,boxstyle='round,pad=0.02,rounding_size=0.12',facecolor='#f7f9fa',edgecolor='#dbe4e8'))
 ax.text(x+.3,5.1,label,fontsize=13,weight='bold',color=color); ax.text(x+.3,4.65,title,fontsize=18,weight='bold',color='#172b3a')
lines=[f'Type: {listing.property_type}',f'Area: {listing.area:g} m²  •  Bedrooms: {listing.bedrooms}',f'Location: {listing.district}',f'Coordinates: {listing.latitude:.6f}, {listing.longitude:.6f}',f'Legal status: {listing.legal_status}']
ax.text(.85,4.08,'\n'.join(lines),fontsize=13,linespacing=1.65,color='#465d6b',va='top')
ax.text(8.95,4.05,f"{result['estimated_price']:.2f} billion VND",fontsize=21,weight='bold',color='#167d8d')
ax.text(8.95,3.43,f"Estimated range: {result['lower_bound']:.2f}–{result['upper_bound']:.2f} billion VND\nModel: {result['model_name']}",fontsize=13,linespacing=1.8,color='#465d6b',va='top')
ax.text(8.95,2.27,f"Listing asking price: {listing.price_range:g} billion VND",fontsize=12,color='#465d6b')
ax.annotate('',xy=(8.42,3.25),xytext=(7.55,3.25),arrowprops=dict(arrowstyle='->',color='#97aab3',lw=2.5))
ax.text(.55,.5,'The asking price is shown for context and is not a model input. The range is a fixed ±12% for apartments.',fontsize=11,color='#718691')
fig.savefig(root/'presentation-figures/forecasting-model-input-output.png',dpi=200,bbox_inches='tight',facecolor='white')
fig.savefig(root/'presentation-figures/forecasting-model-input-output.svg',bbox_inches='tight',facecolor='white')
