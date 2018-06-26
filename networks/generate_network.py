from random import uniform
from networks.network import *
import itertools


def erdos_renyi_network(nodes, p):
    """
    Generate an Erods-Renyi graph with parameter p in (0,1)
    :param nodes:
    :param edges:
    :param p: probability
    :return:
    """
    pairs = list(itertools.combinations(nodes, 2))
    edges = []
    for pair in pairs:
        rand = uniform(0,1)
        if rand < p:
            edges += [pair]
    return Network(nodes, edges)


def star_graph():
    """

    :return:
    """
    nodes = [i for i in range(1,6)]
    edges = [(1,i) for i in nodes if i != 1]
    return Network(nodes, edges)


if __name__ == '__main__':
    G = erdos_renyi_network([2,3,4], 0.5)
    print(G.nodes(), G.edges())