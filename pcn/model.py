import os
from random import random

import time
from pcn import network
from pcn.tx import Tx
from networkx.algorithms.dominating import is_dominating_set
from pcn.agent import PCNAttacker, PcnAgent
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
import re


class PcnModel(Model):
    # Network data

    def __init__(
        self,
        id=(0, 0, 0),
        num_of_agents=Config.DEFAULT_N,
        num_of_steps=Config.SIM_STEPS,
        load_network=False,
        load_tx=False,
        store_network=True,
        store_tx=True,
        attack_model=None
    ):
        super().__init__()
        self.id = id
        self.load_network = load_network
        self.load_tx = load_tx
        self.store_network = store_network
        self.store_tx = store_tx
        self.setup_store()
        self.network = Network(id)
        self.network.setup_network(num_of_agents, load_network, store_network)

        self.attack_model = attack_model
        attackers = attack_model.place_attackers(
            self) if self.attack_model else []

        self.schedule = SimultaneousActivation(self)
        self.grid = NetworkGrid(self.network.G)
        self.num_of_steps = num_of_steps

        # time step track
        self.t = 0

        for node in self.network.G.nodes():
            type = self.network.get_node_type(node)

            if node in attackers:
                agent = PCNAttacker(node, type, self)
            else:
                agent = PcnAgent(node, type, self)
            self.network.payer_list[node] = []
            self.schedule.add(agent)
            self.grid.place_agent(agent, node)

        self.datacollector = DataCollector(
            model_reporters={
                #     "success_tx": self.network.get_success_tx,
                #     "fail_tx": self.network.get_fail_tx,
                #     "fail_tx_timeout": self.network.get_fail_tx_timeout,
                #     "fail_tx_insufficient_fund": self.network.get_fail_tx_insufficient_fund,
                #     "init_tx": self.network.get_init_tx,
                #     "avg_tx_time": self.network.get_avg_time_taken,
                #     "gini": self.network.get_gini
            }
        )

        self.running = True
        self.datacollector.collect(self)

    def set_fee_con_rest(self, agents, type, params=None):
        all_agents = self.get_agents_list()
        rest = list(set(all_agents) - set(agents))
        self.set_fee_con(rest, type, params)

    def set_fee_con(self, agents, type, params=None):
        for agent in self.grid.iter_cell_list_contents(agents):
            agent.setup_fee_con(type, params)

    def get_agents_list(self):
        return self.network.G.nodes

    def get_agents(self, agents):
        return {agent.unique_id: agent for agent in self.grid.iter_cell_list_contents(agents)}

    def setup_store(self):
        dir = Config.file_path(self.id, "")
        try:
            os.makedirs(dir, exist_ok=True)
        except OSError:
            print("Creation of the directory %s failed" % dir)
        if not self.load_tx:
            tx_file = Config.file_path(self.id, Config.FILE_TX)
            open(tx_file, "w")

    def communicate(self, node, tx_id, update=None):
        node = self.grid.iter_cell_list_contents([node])[0]  # pick agent
        node.put(tx_id, update)

    def step(self):
        print(self.id, '******start', self.t, '*********')

        step_txs = []
        G_copy = self.network.G.copy()

        if self.load_tx:
            step_txs = Tx.load_step_txs(self)
        else:
            exclude = self.attack_model.attackers if self.attack_model else []
            step_txs = Tx.generate_txs(self, exclude)

            if self.store_tx:
                Tx.store_tx(self.id, self.t, step_txs)

        if self.attack_model and self.attack_model.amount:  # no saving
            for bt in self.attack_model.bogus_tx(self):
                step_txs.append(bt)

        # save tx in global and agent lists
        for tx in step_txs:
            self.network.tx_list[tx.tx_id] = tx
            self.network.payer_list[tx.source].append(tx.tx_id)

        if self.t == self.num_of_steps-1:
            print("recording", self.id)
            self.record()

        self.schedule.step()
        self.t += 1

        print('******end*********')

    def record(self):
        exhaustion_data = {n: {} for n in self.network.G.nodes()}
        exhausted_failures = {}
        fee_con_data = {}
        for node in self.grid.iter_cell_list_contents(self.network.G.nodes()):
            for n, val in node.exhaustion.items():
                ex_freq = re.findall(r'(1+)', val)
                ex_len = np.array(list(map(len, ex_freq)))
                avg, std = None, None
                if len(ex_len):
                    n = len(ex_len)
                    avg = np.average(ex_len)
                    std = np.std(ex_len)
                    exhaustion_data[node.unique_id].update({n: (avg, std, n)})
            for t, val in node.fee_con.data.items():
                if t in fee_con_data.keys():
                    fee_con_data[t].update({node.unique_id: val})
                else:
                    fee_con_data[t] = {node.unique_id: val}

            exhausted_failures.update(
                {node.unique_id: node.exhausted_failures})

        prefix = str(self.id[2]) + '_'

        # measures = Measures.get_measures(self.network.G.copy())
        # measure_data_file = Config.file_path(self.id, prefix+Config.FILE_MEASURES)
        # json_object = json.dumps(measures)
        # with open(measure_data_file, 'w') as file_object:
        #     file_object.write(json_object+'\n')

        exhaustion_data_file = Config.file_path(
            self.id, prefix+Config.FILE_EXHAUSTION)
        json_object = json.dumps(exhaustion_data)
        with open(exhaustion_data_file, 'w') as file_object:
            file_object.write(json_object+'\n')

        ex_failures_data_file = Config.file_path(
            self.id, prefix+Config.FILE_EX_FAILURES)
        json_object = json.dumps(exhausted_failures)
        with open(ex_failures_data_file, 'w') as file_object:
            file_object.write(json_object+'\n')

        fees_data_file = Config.file_path(self.id, prefix+Config.FILE_FEE)
        json_object = json.dumps(self.network.income)
        with open(fees_data_file, 'w') as file_object:
            file_object.write(json_object+'\n')

        fee_con_data_file = Config.file_path(
            self.id, prefix+Config.FILE_FEE_CON_DATA)
        json_object = json.dumps(fee_con_data)
        with open(fee_con_data_file, 'w') as file_object:
            file_object.write(json_object+'\n')

        # self.datacollector.collect(self)

    def run_model(self):
        for i in range(self.num_of_steps):
            self.step()


class AttackModel:
    def __init__(self):
        self.victim = None
        self.peer = None
        self.attackers = []
        self.amount = 0

    def set_victim(self, victim, peer):
        self.victim = victim
        self. peer = peer

    def set_amount(self, amount):
        self.amount = amount

    def place_attackers(self, model):
        assert model is not None, "Error:Model is not initialized."
        assert model.network is not None, "Error:Network is not initialized."

        N = len(model.network.G.nodes())
        nodes = [
            (N, NodeType.MERCHANT),
            (N+1, NodeType.CLIENT)
        ]
        # node setup
        for (id, type) in nodes:
            model.network.G.add_node(id, type=type.value)
            self.attackers.append(id)
        return self.attackers

    def engage(self, model, attacker, peer, capacity=Config.MAX_CAP):
        assert type(attacker) == int, "Invalid attacker id"
        assert type(peer) == int, "Invalid peer id"
        # channel setup client attacker and victim
        if not model.network.G.has_edge(attacker, peer):
            model.network.G.add_edge(
                attacker, peer, balance=capacity, capacity=capacity, fee=Config.INIT_FEE, locked={})
            model.network.G.add_edge(
                peer, attacker, balance=Config.MAX_CAP, capacity=Config.MAX_CAP, fee=Config.INIT_FEE, locked={})

    def engage_victim(self, model):  # channel setup merchant attcker to peer
        assert self.victim is not None, "Victim not set."
        assert self.peer is not None, "Victim not set."
        self.engage(model, self.attackers[1], self.victim, 3*Config.MAX_CAP)
        self.engage(model, self.peer, self.attackers[0])

    def engage_random(self, model, count):
        neigb = model.network.get_neighbors(self.victim)
        agents = model.get_agents_list()
        r_list = [a for a in agents if model.network.get_node_type(
            a) == NodeType.INTERMEDIARY and a not in neigb]
        for a in r_list[:count]:
            self.engage(model, self.attackers[1], a)

    def bogus_tx(self, model):
        txs = []
        for i in range(self.amount):
            tx = Tx(
                model.t,
                source=self.attackers[1],
                dest=self.attackers[0],
                amount=Config.MIN_AMOUNT,
            )
            path = [tx.source, self.victim, self.peer, tx.dest]
            agents = model.get_agents(path)
            tx.path = tx.set_path(path, agents)
            txs.append(tx)
        return txs
