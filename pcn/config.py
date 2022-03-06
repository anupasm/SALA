from numpy import ceil
from pcn.status import NodeType


class Config:
    # transaction data
    TX_PER_STEP = 100
    PATH_ALGO = 'low_cost_paths'
    MAX_AMOUNT = 10
    MIN_AMOUNT = 4
    ADJUST_AMOUNT = 0

    # tx execution
    EXEC_PROB = 1
    MAX_HOPS = 5
    MAX_RETRY_ATTEMPTS = 5

    # setup params
    DEFAULT_N = 200
    AVG_EDGE_N = 3
    INIT_FEE = 0.01
    MAX_CAP = 100

    MODELS_PER_TEST = 50
    SIM_STEPS = 1000

    # mpc
    MAX_FEE = 0.015
    MIN_FEE = 0.005
    FREQUENCY = 5
    SHOW_OUTPUT = False
    PARAMS_MPC = {
            'f_min': MIN_FEE,
            'f_max': MAX_FEE ,
            'm_min': MIN_AMOUNT+ADJUST_AMOUNT,
            'w_f': 5,
            'w_m': FREQUENCY ,
            'freq': FREQUENCY,
            "out":SHOW_OUTPUT
        }

    PARAMS_OF = {
        's_l': MIN_FEE,
        's_h': MAX_FEE
    }

    # static
    NODE_RATIO = {
        NodeType.MERCHANT: 0.2,
        NodeType.INTERMEDIARY: 0.4,
        NodeType.CLIENT: 0.4
    }

    TX_SEND_WEIGHTS = {
        NodeType.MERCHANT: 3,
        NodeType.INTERMEDIARY: 0,
        NodeType.CLIENT: 7,
    }

    TX_RECEIVE_WEIGHTS = {
        NodeType.MERCHANT: 7,
        NodeType.INTERMEDIARY: 0,
        NodeType.CLIENT: 3,
    }

    def get_node_type_bounds(N):
        b_m = int(ceil(Config.NODE_RATIO[NodeType.MERCHANT] * N))
        b_i = int(ceil(Config.NODE_RATIO[NodeType.INTERMEDIARY] * N)) + b_m
        b_c = N
        return {
            NodeType.MERCHANT: b_m,
            NodeType.INTERMEDIARY: b_i,
            NodeType.CLIENT: b_c
        }

    LOG = 1

    # files
    ROOT = "./data"

    FILE_EXHAUSTION = "exhaustion.json"
    FILE_EX_FAILURES = "ex_failures.json"
    FILE_FEE = "fee.json"
    FILE_MEASURES = "measures.json"
    FILE_NETWORK = "network.json"
    FILE_TX = "tx.json"
    FILE_CONFIG = "config.json"
    FILE_STAT = "stat.json"
    FILE_FEE_CON_DATA = "fee_con_data.json"

    def file_path(id, name):
        return Config.ROOT + "/" + str(id[0]) + "/" + str(id[1]) + "/" + name

    def print(*args):
        if Config.LOG:
            print(str([str(a) for a in args])[1:-1])

    def get_config():
        return {
            "TX_PER_STEP": Config.TX_PER_STEP,
            "PATH_ALGO": Config.PATH_ALGO,
            "MAX_AMOUNT": Config.MAX_AMOUNT,
            "MIN_AMOUNT": Config.MIN_AMOUNT,
            "EXEC_PROB": Config.EXEC_PROB,
            "MAX_HOPS": Config.MAX_HOPS,
            "MAX_RETRY_ATTEMPTS": Config.MAX_RETRY_ATTEMPTS,
            "DEFAULT_N": Config.DEFAULT_N,
            "AVG_EDGE_N": Config.AVG_EDGE_N,
            "INIT_FEE": Config.INIT_FEE,
            "MAX_CAP": Config.MAX_CAP,
            "MODELS_PER_TEST": Config.MODELS_PER_TEST,
            "SIM_STEPS": Config.SIM_STEPS,
            "MAX_FEE": Config.MAX_FEE,
            "MIN_FEE": Config.MIN_FEE,
            "FREQUENCY": Config.FREQUENCY,
            "NODE_RATIO":  list(Config.NODE_RATIO.values()),
            "TX_SEND_WEIGHTS":  list(Config.TX_SEND_WEIGHTS.values()),
            "NODE_RATIO":  list(Config.NODE_RATIO.values())
        }
