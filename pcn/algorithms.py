from typing import OrderedDict
from networkx.algorithms.components.strongly_connected import number_strongly_connected_components
from pcn.status import NodeType
import random
from pcn.config import Config
import networkx as nx
import numpy as np
import sys, timeit
import itertools
import multiprocessing
import statistics


class Route:
 
    def get_path(algo, *attr):
        func = getattr(Route,algo)
        return func(*attr)

    def shortest_path(G,source,dest,amount):
        GG = G.copy()
        low_caps = []
        for u,v in GG.edges:
            if GG[u][v]['capacity'] < amount:
                low_caps.append((u,v))
        GG.remove_edges_from(low_caps)
        try:
            path = nx.shortest_path(GG, source=source, target=dest)
            if G[path[0]][path[1]]['balance'] < amount:#balance with the neighbor is known
                return None
            return path
        except Exception as e:
            return None
    

    def all_paths(G,source,dest,amount):
        GG = G.copy()
        low_caps = []
        for u,v in GG.edges:
            if GG[u][v]['capacity'] < amount:
                low_caps.append((u,v))
        GG.remove_edges_from(low_caps)
        try:
            sorted_paths = list(nx.all_simple_paths(GG, source=source, target=dest, cutoff=Config.MAX_HOPS)) #todo
            sorted_paths.sort(key=lambda x:len(x)) #todo maxmin(x)
            return_paths = []
            count = 0
            for p in sorted_paths:
                if count >= Config.max_retry_attempts: break
                if G[p[0]][p[1]]['weight'] >= amount: #balance with the neighbor is known
                    return_paths.append(p)
                    count += 1                    
            return return_paths
        except Exception as e:
            print("error",e)
            return None

    def low_cost_paths(model, source, dest, amount):
        G = model.network.G.copy()
        def fee_sum(path):
            agents = model.get_agents(path)
            return sum([agents[n1].get_fee(n2,amount) for n1,n2 in zip(path[1:-1], path[2:])])

        low_caps = []
        for u,v in G.edges:
            if G[u][v]['capacity'] < amount:
                low_caps.append((u,v))
        G.remove_edges_from(low_caps)
        # try:
        sorted_paths = list(nx.all_simple_paths(G, source=source, target=dest, cutoff=Config.MAX_HOPS)) #todo
        sorted_paths.sort(key=lambda x:fee_sum(x)) #todo maxmin(x)
        return_paths = []
        count = 0
        for p in sorted_paths:
            if G[p[0]][p[1]]['balance'] >= amount: #balance with the neighbor is known
                return_paths.append(p)
                count += 1                    
        return return_paths
        # except Exception as e:
        #     print("error",e)
        #     return None
    

class TxGen:
    def get_random_amount():
        return int(random.uniform(Config.MIN_AMOUNT,Config.MAX_AMOUNT))

    def get_random_payer_payee(G, exclude=[]):
        w_nodes = OrderedDict({node:Config.TX_SEND_WEIGHTS[NodeType(node_type['type'])] for node,node_type in G.nodes.items() if node not in exclude})
        payer = random.choices(list(w_nodes.keys()),weights=list(w_nodes.values()))[0]
        w_nodes = OrderedDict({node:Config.TX_RECEIVE_WEIGHTS[NodeType(node_type['type'])] for node,node_type in G.nodes.items() if node not in exclude})
        w_nodes.pop(payer)
        payee = random.choices(list(w_nodes.keys()),weights=list(w_nodes.values()))[0]
        return payer, payee

import json
class NetworkCreation:
    def create(N):
        G = nx.empty_graph(N ,create_using=nx.DiGraph())
        nodes = list(G.nodes())
        random.shuffle(nodes) # random assignment
        limits = Config.get_node_type_bounds(N) # get node type according to ratios
        for i,n in enumerate(nodes):
            for node_type in NodeType:
                if i < limits[node_type]:
                    G.nodes[n]['type'] = node_type.value
                    break
        return G

    def get_new_edge(N):
        n1 = random.choices(range(N))[0]
        r = list(range(N))
        r.remove(n1)
        n2 = random.choices(r)[0]
        return n1,n2

    def get_capacity():
        return Config.MAX_CAP,Config.MAX_CAP
        # return int(random.uniform(Config.min_cap,Config.max_cap)),int(random.uniform(Config.min_cap,Config.max_cap))


class Measures:
    FEES = 0
    DEGREE_C = 1
    CLOSENESS_C = 2
    BETWEENESS_C = 3
    PATH_BETWEENESS_C = 4
    RICHNESS = 5
    BALANCEDNESS = 6

    def get_measures(G):
        d_c = nx.degree_centrality(G)
        # c_c = nx.closeness_centrality(G)
        b_c = nx.betweenness_centrality(G)
        p_b, rich, merchant = Measures.get_custom_measures(G)

        measures = {}
        for n in G.nodes:
            item = {
                "d_c":d_c[n],
                # "c_c":c_c[n],
                "b_c":b_c[n],
                "p_b": p_b.get(n,0),
                "rch":rich.get(n,0),
                "bal":merchant.get(n,0),
                "col":int(sum(G[n][i]['capacity'] for i in G.neighbors(n)))
            }
            measures[n]=item
        return measures 

    def _process_pair(G, nodes, n1, n2):

        all_path_min = 0 #all path max min
        n_path_min = dict.fromkeys(list(nodes),0)
        all_path_count = 0
        n_path_count = dict.fromkeys(list(nodes),0)
        merchant_count ={k:0 for k in nodes}
        
        paths = list(nx.all_simple_paths(G, source=n1, target=n2,cutoff=Config.MAX_HOPS ))  #all simple path from n1 to n2
        paths.sort(key=lambda x:len(x)) #todo maxmin(x)
        paths = paths[:Config.MAX_RETRY_ATTEMPTS]
        all_path_count = len(paths) #number of paths with 5 max hops 
        
        for path in paths:   
            offsets = path, path[1:]
            edges = tuple(zip(*offsets))
            min_edge = min(edges, key = lambda x: G[x[0]][x[1]]['capacity'])
            min_val = G[min_edge[0]][min_edge[1]]['capacity']
            for i,n in enumerate(path[1:-1]): #setting values to intermediaries 
                if n_path_min[n] < min_val: n_path_min[n] = min_val  # max min value
                n_path_count[n] += 1 #count
                if NodeType(G.nodes[n2]['type']) == NodeType.MERCHANT:
                    merchant_count[n] += 1
            if all_path_min < min_val: all_path_min = min_val #overall max min value
        return all_path_min, all_path_count, n_path_min, n_path_count, merchant_count

    def get_custom_measures(G):
        #remove zero weighted edges
        edge_weights = nx.get_edge_attributes(G,'capacity')
        G.remove_edges_from((e for e, w in edge_weights.items() if w == 0))
        
        #get connected nodes
        nodes = list(set(G.nodes())-set(nx.isolates(G)))
        total_count = (len(nodes)- nx.number_of_isolates(G) -1)*(len(nodes)-nx.number_of_isolates(G)-2)
        
        richness = dict.fromkeys(nodes,0)
        betweenness = dict.fromkeys(nodes,0)
        merchant_count = {k:0 for k in nodes}
        pool = multiprocessing.Pool()

        inputs = []
        res = []
        for n1 in nodes:
            for n2 in nodes:
                if n1 == n2: continue
                res.append(Measures._process_pair(G,nodes,n1,n2))
                # inputs.append((G,nodes,n1,n2))
        
        # res  = pool.starmap(Measures._process_pair,inputs)
        for r in res:
            all_path_min = r[0]
            all_path_count = r[1]
            n_path_min = r[2]
            n_path_count = r[3]
            m_count = r[4]
            for n in list(nodes):
                if n_path_count[n] and n_path_min[n] and all_path_count and all_path_min:
                    richness[n] += n_path_min[n] / all_path_min 
                    betweenness[n] += n_path_count[n] / all_path_count 
                merchant_count[n] += m_count[n]

        total_m = sum(merchant_count.values())
        
        normal_betweenness, normal_richness, normal_merchant = {}, {}, {} 
        if total_count:
            normal_betweenness = dict(map(lambda kv: (kv[0], kv[1]/total_count), betweenness.items()))
            normal_richness = dict(map(lambda kv: (kv[0], kv[1]/total_count), richness.items()))
        if total_m:
            normal_merchant = dict(map(lambda kv: (kv[0], kv[1]/total_m), merchant_count.items()))
        
        return normal_betweenness, normal_richness, normal_merchant
            