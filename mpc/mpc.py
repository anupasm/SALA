from pcn.config import Config
from sys import path
path.append(r"/home/anupa/Projects/pcn/env/lib/python3.8/site-packages/do-mpc")
path.append(r"/home/anupa/Projects/pcn/env/lib/python3.8/site-packages/do-mpc")
from casadi import *
from do_mpc import *
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.animation import FuncAnimation, ImageMagickWriter
matplotlib.use('TkAgg')

def template_mpc(model, params, CAP, CAP_dash):
    mpc = do_mpc.controller.MPC(model)
    N = len(CAP)
    CAP_total = np.array(CAP)+np.array(CAP_dash)
    setup_mpc = {
        'n_horizon': 20,
        'n_robust': 10,
        'open_loop': 0,
        't_step': 0.001,
        'state_discretization': 'collocation',
        'collocation_type': 'radau',
        'collocation_deg': 2,
        'collocation_ni': 2,
        'store_full_solution': True,
        # 'nlpsol_opts': {'ipopt.linear_solver': 'MA27'}
        # 'nlpsol_opts': {'ipopt.max_iter': 500}
    }
    mpc.set_param(**setup_mpc)


    # Configure objective function:
    lterm = - (model._x['R'])     # Setpoint tracking
    mterm = - (model._x['R'])     # Setpoint tracking

    mpc.set_objective(mterm=mterm, lterm=lterm)
    mpc.set_rterm(F = params['w_f']) 

#     # State and input bounds:

    mpc.bounds['lower', '_u', 'F'] = np.array([params['f_min']]*N)
    mpc.bounds['upper', '_u', 'F'] = np.array([params['f_max']]*N)
    
    mpc.bounds['lower', '_x', 'M'] = np.zeros((N,N))
    mpc.bounds['upper', '_x', 'M'] = np.tile(CAP_total,(N,1))

    # mpc.bounds['lower', '_x', 'B'] = np.array([params['m_min']]*N)
    # mpc.bounds['upper', '_x', 'B'] = CAP_total

    mpc.set_nl_cons('o', sum1(model._x['M']), CAP_total)
    mpc.set_nl_cons('bal_down', -model._x['B'], np.array([params['m_min']]*N))
    mpc.set_nl_cons('bal_up', model._x['B'], CAP_total - params['m_min'])

    mpc.setup()

    return mpc