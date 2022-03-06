import json
from os import error
from typing import OrderedDict
import warnings
from pcn.config import Config
import uuid
from pcn.algorithms import Route, TxGen
from pcn.status import QState, TxState


class Hop:
    def __init__(self, prev, next, status, m_in, m_out, lock):
        self.prev = prev
        self.next = next
        self.status = status
        self.m_in = m_in
        self.m_out = m_out
        self.lock = lock
    
    def is_intermediary(self):
        return self.prev is not None and self.next is not None

    def is_source(self):
        return self.prev is None and self.next is not None

    def is_destination(self):
        return self.prev is not None and self.next is None

    def __str__(self):
        hop = {
            "prev": self.prev,
            "next": self.next,
            "status": self.status,
            "m_in" : self.m_in,
            "m_out" : self.m_out,
            "lock": self.lock
        }
        return str(hop)
        
class Path:
    def __init__(self, ):
        self.path = OrderedDict()

    def get_hop(self, node):
        return self.path[node]
    
    def get_hops(self):
        return self.path.items()

    def set_hop_status(self, node, status):
        self.path[node].status = status

    def get_path(self):
        return 
    
    def __str__(self):
        return str([(node,str(hop.status),'$'+str(hop.m_out)) for node, hop in self.path.items()])
        

class Tx:

    def __init__(
        self,
        t,
        source,
        dest,
        tx_id = None,
        secret = None,
        amount=None,
    ):
        self.source = source   
        self.dest = dest   
        self.amount = TxGen.get_random_amount() if amount is None else amount 
        self.secret = uuid.uuid1() if secret is None else secret
        self.status_updates = dict.fromkeys([t for t in TxState], None)
        self.update_status(TxState.INITIATED, t)
        self.tx_id = hash((self,self.secret)) if tx_id is None else tx_id
        self.failure = None

    def __str__(self):
        return str(self.tx_id) + '@' + str(self.path)+ ' '+ str(self.status) + ' '+ str(self.amount) + ' '+ str(self.failure)

    def set_path(self, path, agents):
        cum_amount = self.amount
        cum_lock = 0
        path.reverse()
        hops = []
        for i,node in enumerate(path):
            status = QState.PENDING
            if i==0: # destination
                next = None
                prev = path[i+1]
                m_in = cum_amount
                m_out = 0
                lock = 0 
            elif i == len(path) - 1: #source
                next = path[i-1]
                prev = None
                m_in = 0
                m_out = cum_amount
                lock = cum_lock + 2 
            else:
                next = path[i-1]
                prev = path[i+1]
                m_out = cum_amount
                fee = agents[node].get_fee(next, self.amount)
                m_in =  cum_amount + fee
                cum_amount = m_in
                lock = cum_lock + 2
                cum_lock = lock
            hop = Hop(prev, next, status, m_in, m_out, lock)
            hops.append((node,hop))

        hops.reverse()
        path_obj = Path()
        path_obj.path = OrderedDict(hops) 
        return path_obj

    def verify(self, secret):
        return self.secret == secret

    def update_status(self,status,step,failure=None):
        self.status = status
        self.status_updates[status] = step
        if status == TxState.FAIL:
            self.failure = failure

    def set_hop_status(self, hop, status):
        self.path.set_hop_status(hop, status)

    def is_success(self):
        return self.status == TxState.SUCCESS

    def is_fail(self):
        return self.status == TxState.FAIL

    # def get_life_time(self):
    #     t_init = 0
    #     if self.retry_status:
    #         t_init = self.retry_status[0][0][TxState.INITIATED]
    #     else:
    #         t_init = self.status_updates[TxState.INITIATED]

    #     t_fail = self.status_updates[TxState.FAIL]
    #     t_success = self.status_updates[TxState.SUCCESS]

    #     if self.is_success():
    #         return t_success - t_init
    #     elif self.is_fail():
    #         return t_fail - t_init
    #     return None


    def get_dict(self):
        return {
            "tx_id":self.tx_id,
            "source": self.source,
            "dest": self.dest,
            "amount": self.amount,
            "secret": str(self.secret),
        }

    #Static methods
    @staticmethod
    def load_step_txs(model):
        t = model.t
        model_id = model.id
        tx_file = Config.file_path(model_id, Config.FILE_TX)
        with open(tx_file, "r") as file_object:
            step_txs = []
            for i, line in enumerate(file_object):
                if i == t:
                    step_data = json.loads(line)[str(i)]
                    for data in step_data:
                        data['amount'] = data['amount'] + Config.ADJUST_AMOUNT 
                        tx = Tx.make_tx(model, data = data)
                        if tx: step_txs.append(tx)
            return step_txs

    @staticmethod
    def generate_txs(model, exclude=[]):
        step_txs = []
        for i in range(Config.TX_PER_STEP):
            tx = Tx.make_tx(model, exclude = exclude)
            if tx:step_txs.append(tx)
        return step_txs
    

    @staticmethod
    def store_tx(model_id,t,step_txs):
        tx_file = Config.file_path(model_id, Config.FILE_TX)
        json_object = json.dumps({t: [tx.get_dict() for tx in step_txs]})
        with open(tx_file, "a") as file_object:
            file_object.write(json_object+'\n')

    @staticmethod
    def make_tx(model, data=None, exclude=[]):
        G = model.network.G.copy()
        t= model.t
        if data is None:
            source, dest = TxGen.get_random_payer_payee(G, exclude)
            tx = Tx(t, source, dest)
        else: 
            tx = Tx(
                t,
                tx_id=data["tx_id"],
                source=data["source"],
                dest=data["dest"],
                secret=data["secret"],
                amount=data["amount"],
            )
        paths = Route.get_path(Config.PATH_ALGO, model, tx.source, tx.dest, tx.amount)
        if not paths: return None 
        
        path = paths[0]
        if len(path) < 2: return None 

        agents = model.get_agents(path)
        tx.path = tx.set_path(path, agents)
        return tx
##########OLD################


# class Tx:

#     def __init__(self, source, dest, secret,step, tx_id = None, amount=None, path=None, candidate_paths=[]):
#         self.source = source
#         self.dest = dest
#         self.amount = amount
#         self.secret = secret
#         self.status_updates = dict.fromkeys([t for t in TxState],None)
#         self.path = path
#         self.candidate_paths = candidate_paths
#         self.selected_path = -1
#         self.failure = None
#         self.tx_id = tx_id if tx_id else hash(self)
#         self.retry_status = {}
#         self.is_finalized = False
#         self.update_status(TxState.INITIATED,step)
    
#     def __str__(self):
#         if self.path:
#             return str(self.tx_id) + '@' + str(self.selected_path) + ' '+ str(self.status) + ' '+ str(self.failure) + ' > '+ str([(x,v[2].name,v[3],v[4]) for x,v in self.path.items()])
#         else:
#             return str(self.tx_id) + '@' + str(self.selected_path)+ ' '+ str(self.status) + ' '+ str(self.failure) + ' '+ str(self.source) + ' '+ str(self.dest)

#     def retry(self, step):
#         if self.selected_path < Config.max_retry_attempts and len(self.candidate_paths) >= self.selected_path + 2: 
#             self.retry_status[self.selected_path] = (self.status_updates,self.failure) # backup prev status
#             self.set_next_path()

#             #re-init
#             self.status_updates = dict.fromkeys([t for t in TxState],None)
#             self.update_status(TxState.INITIATED,step)
#             self.failure = None
#             return True 
#         else:
#             self.is_finalized = True
#             return False 

#     def set_next_path(self):
#         path = self.candidate_paths[self.selected_path+1] + [None] #first path is selected
#         path_amounts = self.reduce_fees(path, self.amount)
#         path_locks = self.set_time_lock(path)
#         offsets = [None] + path[:-1], path[1:] + [None], [QState.PENDING]*(len(path)-1), path_amounts, path_locks
#         path_pairs = OrderedDict(zip(path, zip(*offsets))) #{hop:(prev,next,status,fee, lock)...}
#         self.path = path_pairs
#         self.selected_path = self.selected_path + 1

#     def verify(self, secret):
#         return self.secret == secret

#     def update_status(self,status,step,failure=None):
#         self.status = status
#         self.status_updates[status] = step
#         if status == TxState.FAIL:
#             self.failure = failure
#         if status == TxState.SUCCESS:
#             self.is_finalized = True

#     def is_success(self):
#         return self.status == TxState.SUCCESS

#     def is_fail(self):
#         return self.status == TxState.FAIL

#     def get_life_time(self):
#         t_init = 0
#         if self.retry_status:
#             t_init = self.retry_status[0][0][TxState.INITIATED]
#         else:
#             t_init = self.status_updates[TxState.INITIATED]

#         t_fail = self.status_updates[TxState.FAIL]
#         t_success = self.status_updates[TxState.SUCCESS]

#         if self.is_success():
#             return t_success - t_init
#         elif self.is_fail():
#             return t_fail - t_init
#         return None

#     def get_fees(self,node, amount):
#         return Config.base_fee + amount*Config.col_fee_per

#     def reduce_fees(self,path,amount):
#         path = path[1:-2]
#         amounts = []
#         updated_amount = amount
#         path.reverse()
#         for n in path:
#             updated_amount = updated_amount + self.get_fees(n,amount)
#             amounts.append(updated_amount)
#         amounts.reverse()
#         return amounts + [amount,None]

#     def set_time_lock(self,path):
#         path = path[:-1]
#         locks = []
#         path.reverse()
#         s = 0
#         for i,n in enumerate(path):
#             locks.append(s)
#             s = sum(locks) + 3
#         locks.reverse()
#         return locks + [None]

#     def get_dict(self):
#         return {
#             "tx_id":self.tx_id,
#             "source": self.source,
#             "dest": self.dest,
#             "amount": self.amount,
#             "secret": str(self.secret),
#             "candidate_paths": self.candidate_paths
#         }
