from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
root=Path(__file__).resolve().parent
fig,ax=plt.subplots(figsize=(16,6.5),facecolor='white'); ax.set_xlim(0,16); ax.set_ylim(0,6.5); ax.axis('off')
ax.text(.55,5.95,'Models used for price prediction',fontsize=25,weight='bold',color='#172b3a')
ax.text(.55,5.5,'Three candidate regressors trained on the prepared dataset',fontsize=13,color='#617483')
cards=[('01','Ridge Regression','#167d8d',['StandardScaler preprocessing','alpha = 1.0','fit_intercept = True','solver = auto']),('02','Random Forest','#3277a8',['n_estimators = 150','max_depth = None','min_samples_leaf = 1','random_state = 42','n_jobs = -1']),('03','HistGradientBoosting','#7667a8',['max_iter = 150','learning_rate = 0.1','max_leaf_nodes = 31','min_samples_leaf = 20','random_state = 42'])]
for i,(num,title,color,lines) in enumerate(cards):
 x=.55+i*5.18
 ax.add_patch(FancyBboxPatch((x,1.25),4.82,3.8,boxstyle='round,pad=0.02,rounding_size=0.12',facecolor='#f7f9fa',edgecolor='#dbe4e8',linewidth=1.2))
 ax.text(x+.28,4.55,num,fontsize=15,weight='bold',color=color)
 ax.text(x+.28,4.03,title,fontsize=15,weight='bold',color='#172b3a')
 ax.text(x+.28,3.42,'\n'.join(lines),fontsize=13,linespacing=1.55,color='#465d6b',va='top')
ax.text(.55,.55,'Selected model settings  •  scikit-learn 1.9.1',fontsize=11,color='#718691')
fig.savefig(root/'forecasting-models.png',dpi=200,bbox_inches='tight',facecolor='white')
fig.savefig(root/'forecasting-models.svg',bbox_inches='tight',facecolor='white')
