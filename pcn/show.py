import matplotlib.pyplot as plt
import networkx as nx
import matplotlib.animation as animation
import matplotlib
import numpy as np

matplotlib.use('TkAgg')
plt.ion()

H = nx.octahedral_graph()  # generate a random graph
pos = nx.spring_layout(H, iterations=200)  # find good positions for nodes

def traverse(graph, start, end, steps_between_nodes=50):
    """Generate the new position of the agent.

    :param graph: the graph you want to put your agent to traverse on.
    :param start: the node to start from.
    :param end: the node to end at.
    :param steps_between_nodes: number of steps on each edge.
    """
    steps = np.linspace(0, 1, steps_between_nodes)
    # find the best path from start to end
    path = nx.shortest_path(graph, source=start, target=end)
    stops = np.empty((0, 2))

    for i, j in zip(path[1:], path):
        # get the position of the agent at each step
        new_stops = steps[..., None] * pos[i] + (1 - steps[..., None]) * pos[j]
        stops = np.vstack((stops, new_stops))

    for s in stops:
        yield s

agent_pos = traverse(H, 1, 4)  # make an agent traversing from 1 to 4


def update_position(n):
    plt.cla()
    nx.draw(H, pos, node_size=700, with_labels=True, node_color='green')
    c = plt.Circle(next(agent_pos), 0.05, color='purple', zorder=2, alpha=0.7)
    plt.gca().add_patch(c)


ani = animation.FuncAnimation(plt.gcf(), update_position, interval=30, repeat=False)
plt.ioff()
plt.show()