from collections import OrderedDict
from pcn import model
from pcn.tx import Tx
from networkx.algorithms.similarity import debug_print

from numpy.lib import math
from pcn.config import Config
from pcn.algorithms import Measures, NetworkCreation, TxGen
from pcn.status import Behavior, NodeType, QState, TxFailure, TxState
import networkx as nx
import numpy as np
from enum import Enum
import uuid
import random
import json


class Network:
    def __init__(self, id):
        self.G = None
        self.model_id = id
        self.tx_list = OrderedDict()
        self.payer_list = dict()
        self.income = dict()

    # Network

    def setup_network(self, N, load_network, store_network):
        if load_network:
            # read network data
            network = {}
            network_file = Config.file_path(self.model_id, Config.FILE_NETWORK)
            with open(network_file, "r") as file_object:
                for i, line in enumerate(file_object):
                    network = json.loads(line)

            # init the nodes
            self.G = nx.empty_graph(
                len(network['nodes']), create_using=nx.DiGraph())
            for n, type in network['nodes'].items():
                self.G.nodes[int(n)]['type'] = type['type']

            # init the edges
            for edge in network["edges"]:
                self.create_channel(edge)

        else:
            # random node creation
            self.G = NetworkCreation.create(N)

            # random channel creation
            edge_data = []
            for i in range(Config.AVG_EDGE_N*N):
                edge = self.create_channel()
                if edge:
                    edge_data.append(edge)

            if store_network:  # store network
                network_file = Config.file_path(
                    self.model_id, Config.FILE_NETWORK)
                j_obj = json.dumps({
                    "nodes": dict(self.G.nodes(data=True)),
                    "edges": edge_data,
                })
                with open(network_file, "w") as file_object:
                    file_object.write(j_obj)

    def create_channel(self, data=None):
        assert self.G is not None, "Error: Network is not defined."
        N = len(self.G.nodes())
        if data is None:
            n1, n2 = NetworkCreation.get_new_edge(N)
            c1, c2 = NetworkCreation.get_capacity()
        else:
            n1, n2 = data['edge']
            c1, c2 = data['cap']

        if not self.G.has_edge(n1, n2):
            self.G.add_edge(n1, n2, balance=c1, capacity=c1, locked={})
            self.G.add_edge(n2, n1, balance=c2, capacity=c2, locked={})
            return {'edge': (n1, n2), 'cap': (c1, c2)}
        return None

    # Node

    def is_connected(self, node1, node2):
        return self.G.has_edge(node1, node2)

    def get_payer_tx(self, node):
        return self.payer_list[node]

    def get_tx_hop_data(self, tx_id, node):
        return self.tx_list[tx_id].path.get_hop(node)

    def get_node_behavior(self, node_id):
        return Behavior.LEGIT

    def get_node_type(self, node_id):
        return NodeType(self.G.nodes[node_id]['type'])

    # Transaction

    # queue up the the initiated tx
    def start_init_tx(self, node, step):
        init_tx_list = []
        for tx_id in self.payer_list[node]:
            if self.tx_list[tx_id].status == TxState.INITIATED:
                self.tx_list[tx_id].update_status(TxState.EXECUTING, step)
                init_tx_list.append(tx_id)

        return init_tx_list

    def get_queued_tx(self, queue):
        return dict(filter(lambda item: item[0] in queue, self.tx_list.items())).values()

    def get_tx_status(self, tx_id):
        return self.tx_list[tx_id].status

    def get_tx(self, tx_id):
        return self.tx_list[tx_id]

    def set_tx_queue_status(self, tx_id, hop_id, status):
        self.tx_list[tx_id].path.set_hop_status(hop_id, status)

    # transfer
    def update_balance(self, node1, node2, amount):
        self.G[node1][node2]['balance'] = self.G[node1][node2]['balance'] + amount

    def update_income(self, node, prev, next, received, sent):
        fee = received - sent
        track_id = str(prev)+'-'+str(next)
        if node not in self.income.keys():
            self.income[node] = {track_id: fee}
        else:
            self.income[node][track_id] = self.income[node].get(
                track_id, 0) + fee

    def get_income(self,node):
        if node in self.income.keys():
            return sum(list(self.income[node].values()))
        return 0

    def get_balance(self, node1, node2):
        cap = self.G[node1][node2]['capacity']
        bal = self.G[node1][node2]['balance']
        locked = sum(self.G[node1][node2].get('locked', {}).values())
        return cap, bal, locked

    def lock_balance(self, node1, node2, tx_id, amount):
        self.G[node1][node2]['locked'].update({tx_id: amount})

    def unlock_balance(self, node1, node2, tx_id):
        self.G[node1][node2]['locked'].pop(tx_id, None)

    # Chart
    def get_avg_time_taken(self):
        total = 0
        count = 0
        for t, tx in self.tx_list.items():
            time = tx.get_life_time()
            if time is not None:
                total += time
                count += 1
        return total/count if count > 0 else 0

    def get_success_tx(self):
        count = 0
        for t, tx in self.tx_list.items():
            if tx.status == TxState.SUCCESS:
                count = count + 1
        return count

    def get_fail_tx(self):
        count = 0
        for t, tx in self.tx_list.items():
            if tx.status == TxState.FAIL:
                count = count + 1
        return count

    def get_fail_tx_timeout(self):
        count = 0
        for t, tx in self.tx_list.items():
            if tx.status == TxState.FAIL and tx.failure == TxFailure.TIMEOUT:
                count = count + 1
        return count

    def get_fail_tx_insufficient_fund(self):
        count = 0
        for t, tx in self.tx_list.items():
            if tx.status == TxState.FAIL and tx.failure == TxFailure.INSUFFICIENT_FUNDS:
                count = count + 1
        return count

    def get_init_tx(self):
        count = 0
        for t, tx in self.tx_list.items():
            if tx.status in [TxState.EXECUTING, TxState.INITIATED]:
                count = count + 1
        return count

    def get_gini(self):
        agent_wealths = [v for k, v in self.income.items(
        ) if self.get_node_type(k) == NodeType.INTERMEDIARY]
        x = sorted(agent_wealths)
        N = Config.get_type_count()[NodeType.INTERMEDIARY]
        if N == 0 or sum(x) == 0:
            return 0
        B = sum(xi * (N-i) for i, xi in enumerate(x)) / (N*sum(x))
        return (1 + (1/N) - 2*B)

    def get_tx_total_value(self):
        return sum([t.amount for t in self.tx_list.values()])

    def get_tlv(self):
        return sum([w[2]['capacity'] for w in self.G.edges(data=True)])

    def get_neighbors(self, u):
        return list(self.G.neighbors(u))

    def is_exhausted(self, u, v):
        if self.G[u][v]['balance'] < Config.MIN_AMOUNT and self.G[u][v]['capacity'] > 0:
            return 1
        return 0

    def close_channel(self, u, v, time):
        # print('mmmmmmmmmmmmmmmmmmm',u,v,self.G[u][v],self.G[u][v])
        if not self.G[u][v].get('lock', 0) and not self.G[v][u].get('lock', 0):
            # self.G.remove_edge(u,v)
            # self.G.remove_edge(v,u)
            if (u, v) not in self.closed_channels.keys():
                self.closed_channels[(u, v)] = time
