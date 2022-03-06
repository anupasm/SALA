import math
from pcn.config import Config
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


def template_model(N, params, CAP, CAP_dash):
    model_type = 'discrete'  # either 'discrete' or 'continuous'
    model = do_mpc.model.Model(model_type)
    CAP_total = np.array(CAP)+np.array(CAP_dash)

    M = model.set_variable(var_type='_x', var_name='M', shape=(N, N))
    R = model.set_variable(var_type='_x', var_name='R', shape=(1, 1))
    B = model.set_variable(var_type='_x', var_name='B', shape=(N, 1))
    FD = model.set_variable(var_type='_x', var_name='FD', shape=(N, 1))
    F = model.set_variable(var_type='_u', var_name='F', shape=(N, 1))

    f_min = params['f_min']
    f_max = params['f_max']
    w_m = params['w_m']

    # B_delta = transpose(sum1(M)) - sum2(M) 
    B_delta = transpose(sum1(M)) - sum2(M*(1-FD)) 
    # B_delta = transpose(sum1(M*(F+1))) - sum2(M) 
    model.set_expression('B_delta', B_delta)


    B_next = B + B_delta  

    O_max = repmat(B,(1,N)) 
    model.set_expression('O_max', O_max)

    O_dash = repmat((sum1(B) - B)/(N-1),(1,N)) 
    model.set_expression('O_dash', O_dash)
    print(O_dash)


    # I_max = transpose(CAP_total-O_max)
    I_max = repmat((CAP_total-B),(1,N)) 
    model.set_expression('I_max', I_max)

    # I_norm = I_max/sum1(I_max)
    # model.set_expression('I_norm', I_norm)

    # F_norm = (1/F - 1/f_max)/(1/f_min-1/f_max)
    F_norm = (F-f_min)/(f_max-f_min)
    # F_norm = (Config.INIT_FEE/F - f_min/f_max)/(f_max/f_min-f_min/f_max)
    model.set_expression('F_norm', F_norm)

    # Mi = O_max * transpose(I_max)
    # model.set_expression('Min', Mi)
    # print(Mi)
    # a = (f_min*M + f_max*(I_max-M) - FD*I_max)/((f_min-f_max)*(f_min-FD)*(f_max-FD))
    # b = (I_max/(f_min-f_max)) - a*(f_min+f_max)
    # c = I_max - a*f_min**2 - b*f_min

    # print(a)
    # print(b)
    # print(c)
    # model.set_expression('a', a)
    # model.set_expression('b', b)
    # model.set_expression('c', c)
    # M_next = O_norm*transpose(I_max)*F_norm #*transpose(repmat(I_norm,(1,N)))
    # M_next =  transpose(I_max)*M/(sum2(M)+1)
    # M_next =  fmax(O_max,transpose(I_max))*F_norm
    M_next =  (w_m/N)*(O_max*F_norm)
    # M_next =  *I_max*F_norm
    # M_next =  np.tile(CAP_total,(N,1))*(1/F)
    # M_next = w_m*np.tile(CAP_total,(N,1))*F_norm
    # M_next = w_m*I_max*F_norm
    # M_next = a*F**2 + b*F + c
    # M_next = I_max - ((I_max-M)*(F-f_min))/(FD-f_min)
    # M_next = (M*(f_max-F))/(f_max-FD)
    print(M_next)
    R_next = R + sum2(sum1(FD*M))
    # B_next = B_delta  

    model.set_rhs('R', R_next)
    model.set_rhs('B', B_next)
    model.set_rhs('M', M_next)
    model.set_rhs('FD', F)

    # Setup model:
    model.setup()

    return model
