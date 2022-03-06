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


def template_simulator(model):
    simulator = do_mpc.simulator.Simulator(model)

    params_simulator = {
        't_step': 1.0
    }
    simulator.set_param(**params_simulator)
    simulator.setup()
    return simulator