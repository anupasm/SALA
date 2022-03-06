from enum import Enum


class QState(Enum):
    PENDING = 0
    PASSED = 1
    RETURN = 2
    FAIL_RETURN = 3

    def __str__(self):
        return self.name

class TxState(Enum):
    INITIATED = 0
    EXECUTING = 1
    SUCCESS = 2
    FAIL = 3

    def __str__(self):
            return '%s' % self.name

class TxFailure(Enum):
    TIMEOUT = 1
    INSUFFICIENT_FUNDS = 2
    INVALID_SECRET = 3

    def __str__(self):
            return '%s' % self.name

class NodeType(Enum):
    MERCHANT = 0
    INTERMEDIARY = 1
    CLIENT = 2

class Behavior(Enum):
    LEGIT = 0 
    PASSIVE = 1
    ACTIVE = 2


class FeeConType(Enum):
    STATIC_FEE = 0
    MPC_FEE = 1
    OPTIMIZEDFEE = 2