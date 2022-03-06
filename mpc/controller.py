
from numpy.lib import math
from mpc.simulator import template_simulator
from mpc.model import template_model
from mpc.mpc import template_mpc
from sys import path

from pcn.config import Config
from pcn.status import FeeConType
path.append(r"/home/anupa/Projects/pcn/env/lib/python3.8/site-packages/do-mpc")
path.append(r"/home/anupa/Projects/pcn/env/lib/python3.8/site-packages/do-mpc")
from casadi import *
from do_mpc import *
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.animation import FuncAnimation, ImageMagickWriter
matplotlib.use('TkAgg')


class FeeController:
    
    def __init__(self, peers, CAP, CAP_dash):
        self.peers = peers
        self.M = {i:{j:0 for j in peers} for i in peers}
        self.B = {i:CAP[i] for i,p in enumerate(peers)}
        self.L = {i:CAP[i] for i,p in enumerate(peers)}
        self.r = 0
        self.t = 0
        self.data = {}

    def update_M(self, prev, next, amount):
        self.M[prev][next] = self.M[prev][next] + amount

    def update(self, t, r, B, L):
        self.B = {i:B[i] for i,p in enumerate(self.peers)}
        self.L = {i:L[i] for i,p in enumerate(self.peers)}
        self.r = r
        self.t = t
        self.data[t] = {'b':self.B,'r':self.r,'m':self.M, 'l':self.L}
        self.M = {i:{j:0 for j in self.peers} for i in self.peers}

    def get_fee(self, peer, amount):
        raise NotImplementedError("Please Implement this method")

class StaticFeeCon(FeeController):
    def __init__(self, peers, CAP, CAP_dash, static_fee):
        super().__init__(peers, CAP, CAP_dash)
        self.static_fee = static_fee

    def get_fee(self, peer, amount):
        return self.static_fee * amount


class OptimizedFeeCon(FeeController):
    def __init__(self, peers, CAP, CAP_dash, params):
        self.params = params
        self.total_cap =  np.array(CAP) + np.array(CAP_dash)
        super().__init__(peers, CAP, CAP_dash)

    def get_fee(self, peer, amount):
        for i, agent in enumerate(self.peers):
            if agent == peer:
                ab = self.B[i]
                ba = self.total_cap[i] - self.B[i]
                imb = abs(ab-ba)
                if ab>ba:
                    if amount>imb/2:
                        return imb/2*self.params['s_l'] + (amount-imb/2)*self.params['s_h']
                    else:
                        return amount*self.params['s_l']
                else:
                    return amount*self.params['s_h']
        return None

class MPCFeeCon(FeeController):
    def __init__(self, peers, CAP, CAP_dash,  params):
        super().__init__(peers, CAP, CAP_dash)
        self.fees = {i:Config.INIT_FEE for i in peers}
        self.params = params
        self.init_mpc(CAP, CAP_dash)
        if params['out']:
            self.setup_graphic()

    def init_mpc(self, CAP, CAP_dash):
        N = len(self.peers)
        self.model = template_model(N, self.params, CAP, CAP_dash)
        self.mpc = template_mpc(self.model, self.params, CAP, CAP_dash)
        M0 = [0]*(N*N)
        r0 = [0]
        B0 = CAP
        F0 = [Config.INIT_FEE]*N
        self.x0 = np.array(M0+r0+B0+F0).reshape(-1,1)
        self.mpc.x0 = self.x0
        self.mpc.u0 = np.array(F0).reshape(-1,1)
        self.mpc.set_initial_guess()

    def setup_graphic(self):
        # Initialize graphic:
        self.mpc_graphics = do_mpc.graphics.Graphics(self.mpc.data)

        fig, ax = plt.subplots(6, sharex=True, figsize=(16,9))
        # Configure plot:
        self.mpc_graphics.add_line(var_type='_x', var_name='B', axis=ax[0])
        self.mpc_graphics.add_line(var_type='_x', var_name='R', axis=ax[1])
        self.mpc_graphics.add_line(var_type='_u', var_name='F', axis=ax[2])
        self.mpc_graphics.add_line(var_type='_x', var_name='M', axis=ax[3])
        self.mpc_graphics.add_line(var_type='_aux', var_name='F_norm', axis=ax[4])
        self.mpc_graphics.add_line(var_type='_aux', var_name='O_max', axis=ax[5])

        ax[0].set_ylabel('B')
        ax[1].set_ylabel('R')
        ax[2].set_ylabel('F')
        ax[3].set_ylabel('M')
        ax[4].set_ylabel('F_norm')
        ax[5].set_ylabel('O_max')

        bal_lines = self.mpc_graphics.result_lines['_x', 'B']
        ax[0].legend(bal_lines, self.peers)

        # I_lines = self.mpc_graphics.result_lines['_aux', 'I_max']
        # ax[4].legend(I_lines, [self.peers]*len(self.peers))


        fee_lines = self.mpc_graphics.result_lines['_u', 'F']
        ax[2].legend(fee_lines, self.peers)

        fig.align_ylabels()
        plt.ion()        


    def update(self, t, r, B, L):
        if t%self.params['freq']==0:
            f = self.make_step(t, r, B) 
            f_list = f.flatten().tolist()
            for i, p in enumerate(self.peers):
                self.fees[p] = f_list[i]                
            super().update(t, r, B, L)
            self.data[t]['f'] = {i:self.fees[p] for i,p in enumerate(self.peers)}

    def get_fee(self, peer, amount):
        return self.fees[peer]*amount

    def make_step(self, t, r, B):
        M = np.matrix([[min(self.M[j][i],2*Config.MAX_CAP) for j in self.peers] for i in self.peers])
        print(self.peers)
        print('R')
        print(r)
        print('B')
        print(B)
        print('M')
        print(M)
        fee_rates = [self.get_fee(p,1) for p in self.peers]
        x = np.array(M.flatten().tolist()[0] + [r] + B + fee_rates)
        u_new = self.mpc.make_step(x.reshape(-1,1))
        print('f',u_new)
        if self.params['out']:
            self.show(int(t/self.params['freq']))
        return u_new

    def show(self, k):
        self.mpc_graphics.plot_results(t_ind=k)
        self.mpc_graphics.plot_predictions(t_ind=k)
        self.mpc_graphics.reset_axes()
        plt.show()
        plt.pause(0.04)
        
    def save(self):
        do_mpc.data.save_results([self.mpc], 'pcn_data')



# print(self.unique_id,'time',self.model.t )

# print('R')
# print(R)
# print('B')
# print(B)
# print('M')
# print(M)
# print('F')
# print([self.model.network.G[self.unique_id][p]['fee'] for i, p in enumerate(self.fee_con.peers)])
