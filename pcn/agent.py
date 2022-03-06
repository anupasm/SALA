import re
from typing import Counter
from casadi.casadi import integrator_out
from networkx.algorithms.graphical import is_valid_degree_sequence_erdos_gallai
from networkx.classes.function import neighbors
from mpc.controller import MPCFeeCon, OptimizedFeeCon, StaticFeeCon
from do_mpc import controller
from pcn.config import Config
from pcn.status import FeeConType, NodeType, QState, TxFailure, TxState
from pcn.algorithms import Measures, NetworkCreation, TxGen
from pcn.network import Network
from mesa import Agent, Model
from mesa.time import RandomActivation, SimultaneousActivation
from mesa.space import NetworkGrid
from mesa.datacollection import DataCollector
import networkx as nx
import numpy as np
from enum import Enum, unique
import uuid
import json
from collections import OrderedDict


class PcnAgent(Agent):

    def __init__(self, unique_id, node_type,  model):
        super().__init__(unique_id, model)
        self.queue = dict()
        self.track_tx = dict()  # personally track tx time {tx:time}
        self.node_type = node_type
        self.exhaustion = dict()
        self.exhausted_failures = {}

    def setup_fee_con(self, fee_con_type, params=None):#not supporting dynamic network
        peers = self.model.network.get_neighbors(self.unique_id)
        CAP = [self.model.network.G[self.unique_id][n]['capacity'] for n in peers]
        CAP_dash = [self.model.network.G[n][self.unique_id]['capacity'] for n in peers]

        if fee_con_type == FeeConType.STATIC_FEE:
            self.fee_con = StaticFeeCon(peers, CAP, CAP_dash, Config.INIT_FEE)
        elif fee_con_type == FeeConType.MPC_FEE:
            self.fee_con = MPCFeeCon(peers, CAP, CAP_dash, params)
        elif fee_con_type == FeeConType.OPTIMIZEDFEE:
            self.fee_con = OptimizedFeeCon(peers, CAP, CAP_dash, params)

    def put(self, tx_id, update=None):  # receive queue update from peers
        self.queue.update({tx_id: update})

    def get_balance(self, peer):
        capacity, balance, locked = self.model.network.get_balance(self.unique_id, peer)
        return balance, locked

    def get_fee(self, peer, amount):
        return self.fee_con.get_fee(peer,amount)

    def update_fee_con(self):
        assert self.fee_con is not None, "Fee controller is not setup."

        B = [self.get_balance(p)[0]-self.get_balance(p)[1] for p in self.fee_con.peers]
        L = [self.get_balance(p)[1] for p in self.fee_con.peers]
        r = self.model.network.get_income(self.unique_id)
        self.fee_con.update(self.model.t, r, B, L)

    def lock_balance(self, peer, tx_id, amount):
        self.model.network.lock_balance(
            self.unique_id, peer, tx_id, amount)

    def is_transferable(self, peer, amount):
        balance, locked = self.get_balance(peer)
        return balance - locked >= amount

    def track(self, tx, t):
        if t is not None:
            self.track_tx.update({tx: t})  # start tracking
        else:  # remove tracking
            self.track_tx.pop(tx)

    def forward(self, tx, hop):
        if not hop.is_destination():  # pass forward
            # check sufficient balnce
            if self.is_transferable(hop.next, hop.m_out):  # adequate balance
                tx.set_hop_status(self.unique_id, QState.PASSED)
                self.lock_balance(hop.next, tx.tx_id, hop.m_out)
                self.track(tx, self.model.t)  # start tracking
                self.model.communicate(hop.next, tx.tx_id)
            else:  # fail to transfer
                tx.set_hop_status(self.unique_id, QState.FAIL_RETURN)
                if not hop.is_source():
                    self.model.communicate(
                        hop.prev, tx.tx_id, TxFailure.INSUFFICIENT_FUNDS)
                    if tx.dest != 50:
                        self.exhausted_failures[hop.next] = self.exhausted_failures.get(hop.next,0) + hop.m_in - hop.m_out 
                    
                else:  # fail to forward at source -- not possible
                    tx.update_status(
                        TxState.FAIL, self.model.t, TxFailure.INSUFFICIENT_FUNDS)
                    # self.restart(tx) xxxxxxxxxxxxxxxxxx
        else:  # destination
            tx.set_hop_status(self.unique_id, QState.RETURN)

            # provide the secret
            self.reveal_secret(hop.prev, tx.tx_id, tx.secret)

        self.queue.pop(tx.tx_id)

    def reveal_secret(self, prev, tx_id, secret):
        self.model.communicate(prev, tx_id, secret)

    def restart(self, tx):
        for node in self.model.grid.iter_cell_list_contents(list(tx.path.keys())[1:]):
            node.queue.pop(tx.tx_id, None)
            node.track_tx.pop(tx, None)

        if tx.retry(self.model.time_step):
            self.model.network.tx_list[tx.tx_id] = tx
            self.model.network.payer_list[tx.source].append(tx.tx_id)

    def settle(self, tx):
        for node, hop in tx.path.get_hops():
            # unlock the balances
            if not hop.is_destination():
                self.model.network.unlock_balance(node, hop.next, tx.tx_id)

            if tx.is_success():
                # payment update
                if not hop.is_destination():  # except last
                    self.model.network.update_balance(
                        node, hop.next, -1 * hop.m_out)
                    self.model.network.update_balance(
                        hop.next, node, hop.m_out)
                # fee update
                if hop.is_intermediary():  # intermediary
                    self.model.network.update_income(node, hop.prev, hop.next, hop.m_in, hop.m_out)

    def backward(self, tx, hop, msg):
        is_verified = tx.verify(msg)
        if not hop.is_source():  # intermediary
            self.model.communicate(hop.prev, tx.tx_id, msg)
            if is_verified:
                tx.set_hop_status(self.unique_id, QState.RETURN)
            else:
                tx.set_hop_status(self.unique_id, QState.FAIL_RETURN)
        else:  # source
            if is_verified:
                tx.set_hop_status(self.unique_id, QState.RETURN)
                tx.update_status(TxState.SUCCESS, self.model.t)
            else:
                tx.update_status(
                    TxState.FAIL, self.model.t, msg)  # msg is the error
                tx.set_hop_status(self.unique_id, QState.FAIL_RETURN)
                # self.restart(tx) xxxxxxxxxxxxxxxxxxxxxxx

            self.settle(tx)  # settle the balances

        self.track(tx, None)  # remove from tracking
        self.queue.pop(tx.tx_id)

    def process_tx(self, tx, msg):
        hop = self.model.network.get_tx_hop_data(tx.tx_id, self.unique_id)
        if type(self.fee_con) != StaticFeeCon and hop.next:
            Config.print(self.unique_id,self.get_fee(hop.next, tx.amount), 'fee',(hop.m_in-hop.m_out),tx.amount, self.model.network.tx_list[tx.tx_id])

        if hop.status == QState.PENDING:
            self.forward(tx, hop)
        elif hop.status == QState.PASSED:
            self.backward(tx, hop, msg)
        else:
            self.queue.pop(tx.tx_id)

        return hop


    def step(self):
        self.update_fee_con()

        # start executing generated tx
        init_txs = self.model.network.start_init_tx(
            self.unique_id, self.model.t)
        self.queue.update({t: None for t in init_txs})

        # probabilistic occurrence
        size = len(self.queue.keys())
        probs = [1-Config.EXEC_PROB, Config.EXEC_PROB]
        occurrence = np.random.choice([0, 1], size=size, p=probs)

        # process  received tx
        queued_txs = self.model.network.get_queued_tx(self.queue.keys())

        for i, tx in enumerate(queued_txs):
            msg = self.queue[tx.tx_id]
            if occurrence[i]:
                hop_data = self.process_tx(tx, msg)
                if self.fee_con and hop_data.is_intermediary():# and hop_data.status == QState.PASSED:
                    self.fee_con.update_M(hop_data.prev, hop_data.next, tx.amount)

        self.monitor_timeout() # Timeout Check
        self.exhaustion_check() # Exhaustion check


    def monitor_timeout(self):
        # if self.track_tx:
        #     Config.print(self.unique_id, 'track', self.track_tx)

        remove = []
        for tx, start_time in self.track_tx.items():
            time = self.model.t - start_time
            hop = self.model.network.get_tx_hop_data(tx.tx_id, self.unique_id)
            if hop.lock < time:

                # Config.print(self.unique_id, 'time exceed')

                if not hop.is_source():  # pass msg
                    self.model.communicate(
                        hop.prev, tx.tx_id, TxFailure.TIMEOUT)
                else:  # source
                    tx.update_status(
                        TxState.FAIL, self.model.t, TxFailure.TIMEOUT)

                    # restarting
                    # self.restart(tx)xxxxxxxxxxxxxxxxxxxxxxx

                    # release lock balances
                    self.settle(tx)

                tx.set_hop_status(self.unique_id, QState.FAIL_RETURN)
                remove.append(tx.tx_id)

        # remove all timeout tx from tracking
        for t in remove:
            self.track(t, None)

    def exhaustion_check(self):
        neighbors = self.model.network.get_neighbors(self.unique_id)
        for v in neighbors:
            is_exhausted = self.model.network.is_exhausted(self.unique_id, v)
            self.exhaustion[v] = self.exhaustion.get(v,"") + str(is_exhausted)

class PCNAttacker(PcnAgent):
    def __init__(self, unique_id, node_type,  model):
        super().__init__(unique_id, node_type,  model)

    def reveal_secret(self, prev, tx_id, secret):
        return super().reveal_secret(prev, tx_id, None)




