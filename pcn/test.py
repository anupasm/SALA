import math
from matplotlib.animation import FuncAnimation, ImageMagickWriter
import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import matplotlib
from do_mpc import *
from casadi import *
from casadi.tools import *

from sys import path
path.append(r"/home/anupa/Projects/pcn/env/lib/python3.8/site-packages/do-mpc")
path.append(r"/home/anupa/Projects/pcn/env/lib/python3.8/site-packages/do-mpc")
matplotlib.use('TkAgg')


B =np.array([10,180,30])
C =np.array([100,200,300])
print(repmat(B,(1,3)))
print(transpose(repmat(B,(1,3))))
print(C)
print(transpose(C-repmat(B,(1,3))))
print(fmin(repmat(B,(1,3)),transpose(C-repmat(B,(1,3)))))



K=np.array([[10,180,30],[0,80,0],[1,18,3]])
Y=np.array([[100,18,300],[0,80,0],[1,18,3]])
print(fmin(K,Y))


cm = np.tile(C,(3,1))
bm = np.tile(B,(3,1))
print(cm)
print(transpose(bm))
print(cm+transpose(bm))
