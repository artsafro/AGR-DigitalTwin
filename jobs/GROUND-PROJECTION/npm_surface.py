"""Smooth heightfield interpolation shared by construction and verification."""
import numpy as np
class Field:
 def __init__(self,path):
  d=np.load(path);self.x=d['xs'];self.y=d['ys'];self.z=d['height'];self.step=self.x[1]-self.x[0]
 def sample(self,xy):
  xy=np.asarray(xy);shape=xy.shape[:-1];q=xy.reshape(-1,2);ux=(q[:,0]-self.x[0])/self.step;uy=(q[:,1]-self.y[0])/self.step
  ix=np.floor(ux).astype(int);iy=np.floor(uy).astype(int);tx=ux-ix;ty=uy-iy
  def weights(t):return np.stack((-.5*t+t*t-.5*t**3,1-2.5*t*t+1.5*t**3,.5*t+2*t*t-1.5*t**3,-.5*t*t+.5*t**3),axis=1)
  wx=weights(tx);wy=weights(ty);out=np.zeros(len(q))
  for j in range(4):
   for i in range(4):out+=wx[:,i]*wy[:,j]*self.z[np.clip(iy+j-1,0,len(self.y)-1),np.clip(ix+i-1,0,len(self.x)-1)]
  return out.reshape(shape)
