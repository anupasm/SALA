from enum import unique
import math
from pcn.algorithms import Measures
from pcn.status import NodeType

from mesa.visualization.ModularVisualization import ModularServer
from mesa.visualization.UserParam import UserSettableParameter
from mesa.visualization.modules import ChartModule
from .visualize import NetworkModule
from mesa.visualization.modules import TextElement
from .model import PcnAgent,PcnModel
from mesa.visualization.modules import (
    ChartModule,
    BarChartModule,
)

def network_portrayal(G):

    def edge_label(source, target):
        return str(round(G[source][target]["balance"],2)) + '/' + str(G[source][target]["capacity"]) 
        # return str(source) +'>'+ str(target) +':'+ str(G[source][target]["weight"])


    def node_color(agent):
        if agent.node_type == NodeType.CLIENT:
            return "#008000"
        elif agent.node_type == NodeType.MERCHANT:
            return "#ff8100"
        elif agent.node_type == NodeType.INTERMEDIARY:
            return "#0045ff"

    def tooltip(agent):
        GG = G.copy()
        return str(agent.unique_id) + '-' + str(agent.node_type).split('.')[1]

    portrayal = dict()
    if G.nodes:
        portrayal["nodes"] = [
            {
                "id":agents[0].unique_id,
                "label":str(agents[0].unique_id),
                "color": node_color(agents[0]),
                "size": 10,
                "tooltip":tooltip(agents[0]),
            }
            for (_, agents) in G.nodes.data("agent")
        ]

        portrayal["edges"] = [
            {
                "id":i,
                "source": source,
                "target": target,
                "color":"#808080",
                "label":edge_label(source,target),
            }
            for i,(source, target) in enumerate(G.edges)
        ]

    return portrayal


network = NetworkModule(network_portrayal, 700, 1000)

model_bar = BarChartModule(
    [
        {"Label": "success_tx", "Color": "#46FF33"},
        {"Label": "fail_tx", "Color": "#FF3C33"},
        {"Label": "init_tx", "Color":  "#3349FF"},
    ],
    canvas_height=500,
    canvas_width=500
)

class TxCountsElement(TextElement):
    def __init__(self):
        pass

    def render(self, model):
        return ' Success: ' +str(model.network.get_success_tx()) + \
            ' Fail ' + str(model.network.get_fail_tx()) + \
            ' (Timeout ' + str(model.network.get_fail_tx_timeout()) + \
            ' Insufficient Funds ' + str(model.network.get_fail_tx_insufficient_fund()) + \
            ') Init: ' + str(model.network.get_init_tx()) + \
            ' <br>TLV: ' + str(model.network.get_tlv()) + \
            '  tx_total ' + str(model.network.get_tx_total_value()) 

time_chart = ChartModule([{"Label": "avg_tx_time",
                      "Color": "Black"}],
                    data_collector_name='datacollector')

count_element = TxCountsElement()

gini_chart = ChartModule([{"Label": "gini",
                      "Color": "Black"}],
                    data_collector_name='datacollector')

# model_params = {
#     "nodes_total": UserSettableParameter('slider', 'Total Nodes', value=7, min_value=3, max_value=1000, step=10)
# }


server = ModularServer(
    PcnModel, [network,count_element,time_chart,gini_chart], "PCN Model",
)
server.port = 8521
