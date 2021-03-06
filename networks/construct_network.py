import graph_tool.all as gt
import numpy as np
import random
from math import exp

from ext import globals
from ext.threshold_functions import sigmoid
from ext.tools import prod

S = [1, 1, 1, 1]            # White color
I = [0, 0, 0, 1]            # Black color
R = [0.5, 0.5, 0.5, 1.]     # Grey color

class Network(gt.Graph):
    def __init__(self, vertices=None, edges=None, defaults=True, model='SIR', threshold='relative'):
        super().__init__(directed=False)
        # Setting up all properties of the graph
        self.gp['model'] = self.new_gp('string', val=model)
        self.gp['threshold'] = self.new_gp('string', val=threshold)
        self.vp['id'] = self.new_vp('int')
        self.vp['infectious_time'] = self.new_vp('int')
        self.vp['initial_infectious_time'] = self.new_vp('int')
        self.vp['recovered_time'] = self.new_vp('int')
        self.vp['initial_recovered_time'] = self.new_vp('int')
        self.vp['security'] = self.new_vp('double')
        self.vp['utility'] = self.new_vp('double')
        self.vp['threshold_value'] = self.new_vp('double') # complex contagion
        self.vp['state'] = self.new_vp('vector<double>') # for animation
        self.vp['recovered'] = self.new_vp('bool')
        self.vp['infectious'] = self.new_vp('bool')
        self.vp['susceptible'] = self.new_vp('bool')
        self.vp['attack_decision'] = self.new_vp('double')
        self.vp['hide'] = self.new_vp('bool') # for network effect calculation
        self.vp['layer'] = self.new_vp('int')
        self.ep['rate'] = self.new_ep('double')
        if vertices is not None:
            self.add_vertex(vertices)
            if edges is not None:
                self.add_edge_list(edges)
            if defaults:
                self._default_properties()

    @classmethod
    def from_graph(cls, G, defaults=True, model='SIR', threshold='relative'):
        """
        Generates a network via a graph object from graph_tool

        :param G: graph object
        :return:
        """
        return cls(vertices=G.num_vertices(), edges=list(G.edges()), defaults=defaults, model=model, threshold=threshold)

    def _default_properties(self):
        """
        Initializes the default properties of the network simulation

        :return:
        """
        low, high, n, m = globals.START_TIME, globals.STOP_TIME, self.num_vertices(), self.num_edges()
        infect, recover = np.random.randint(low, high, n), np.random.randint(low, high, n)

        if self.gp['threshold'] == 'absolute':
            threshold_values = np.random.randint(1, 5, n)
        elif self.gp['threshold'] == 'relative' or self.gp['threshold'] == 'probabilistic':
            threshold_values = np.random.random(n)

        self.vp['id'].a = list(range(self.num_vertices()))
        self.vp['infectious_time'].a = infect
        self.vp['initial_infectious_time'].a = infect
        self.vp['recovered_time'].a = recover
        self.vp['initial_recovered_time'].a = recover
        self.vp['security'].a = np.random.rand(n)
        self.vp['utility'].a = 0
        self.vp['threshold_value'].a = threshold_values
        self.vp['state'].set_value(S)
        self.vp['recovered'].a = False
        self.vp['infectious'].a = False
        self.vp['susceptible'].a = True
        self.vp['attack_decision'].a = 1/n
        self.vp['hide'].a = False
        self.vp['layer'].a = -1
        self.ep['rate'].a = np.random.rand(m)

    def get_transmissibility(self, u, v):
        """
        Calculates the transmissibility between two nodes in the network

        :param u: vertex object or vertex index
        :param v: vertex object or vertex index
        """
        edge = self.edge(u, v)
        return 1 - exp(-self.ep['rate'][edge] * self.vp['infectious_time'][u])

    def infect_vertex(self, v, complex=False, f=sigmoid):
        """
        Attempts to infect vertex v
        :param v: vertex object or vertex index
        :return: True if vertex was infectious, False otherwise
        """
        if complex:
            neighbors = self.vertex(v).out_neighbors()
            active_neighbors = [idx for idx in neighbors if self.vp['infectious'][idx]]

            relative = (self.gp['threshold'] == 'relative' and len(active_neighbors) / self.vertex(v).out_degree() >= self.vp['threshold_value'][v])
            absolute = (self.gp['threshold'] == 'absolute' and len(active_neighbors) >= self.vp['threshold_value'][v])
            probabilistic = (self.gp['threshold'] == 'probabilistic' and random.random() >= f(len(active_neighbors)/neighbors))
            if not (relative or absolute or probabilistic):
                return False
        elif random.random() < self.vertex_properties['security'][v]:
            return False

        print('Infecting vertex {}'.format(v), absolute)
        print('Neighbors {}, active neighbors {} :'.format(neighbors, active_neighbors))
        print('Active neighbors {} / threshold {}'.format(len(active_neighbors), self.vp['threshold_value'][v]))
        self.vp['infectious'][v] = True
        self.vp['susceptible'][v] = False
        self.vp['state'][v] = I
        return True

    def update_infectious_time(self):
        """
        Update infectious time and current state

        :return:
        """
        self.set_vertex_filter(self.vp['infectious'])

        self.vp['infectious_time'].ma -= 1
        mask = self.vp['infectious_time'].ma == 0
        self.vp['infectious_time'].ma[mask] = self.vp['initial_infectious_time'].ma[mask]
        self.vp['infectious'].ma[mask] = False
        self.vp['recovered'].ma[mask] = True

        newly_recovered = self.new_vp("bool")
        newly_recovered.a = False
        newly_recovered.ma[mask] = True

        self.set_vertex_filter(newly_recovered)
        self.vp['state'].set_value(R)

        self.clear_filters()

        return

    def update_recovered_time(self):
        """
        Update recovered time and current state

        :return:
        """
        self.set_vertex_filter(self.vp['recovered'])

        self.vp['recovered_time'].ma -= 1
        mask = self.vp['recovered_time'].ma == 0
        self.vp['recovered_time'].ma[mask] = self.vp['initial_recovered_time'].ma[mask]
        self.vp['recovered'].ma[mask] = False
        self.vp['susceptible'].ma[mask] = True

        newly_susceptible = self.new_vp("bool")
        newly_susceptible.a = False
        newly_susceptible.ma[mask] = True

        self.set_vertex_filter(newly_susceptible)
        self.vp['state'].set_value(S)

        self.clear_filters()

        return

    def compute_externality(self, i, j):
        """
        Calculates externality of vertex i on j
        :param i: vertex object or vertex index
        :param j: vertex object or vertex index
        :return:
        """
        # TODO : Figure out how to calculate paths using graph_tools
        Q_ij = 0
        for v in self.vertices():
            for path in gt.all_paths(self, v, i):
                if j in path:
                    transmission = prod([(1 - self.vp['security'][k]) for k in path[1:]])
                    Q_ij += self.vp['attack_decision'][v] * (1 - self.vp['security'][v]) * transmission

        return (1 - self.vp['security'][j]) * Q_ij

    def compute_infection_probability(self, i):
        """

        :return:
        """
        print(self.num_vertices())
        if self.num_vertices() == 1:
            return self.vp['attack_decision'][self.get_vertices()[0]]

        while True:
            j = random.choice(self.get_vertices())
            if j != i: break

        externality = self.compute_externality(i,j)

        self.vp['hide'][j] = True
        self.set_vertex_filter(self.vp['hide'], inverted=True)
        return self.compute_infection_probability(i) + externality

    def compute_network_effect(self, i):
        """
        Calculates probability of infection reaching agent i, i.e network effect on i
        :param i: vertex object or vertex index
        :return:
        """
        # TODO fix network effect computation
        network_effect = (1 - self.vp['security'][i]) * self.compute_infection_probability(i)
        self.vp['hide'].a = False
        self.clear_filters()
        return network_effect

    def compute_social_welfare(self):
        """
        Computes social welfare
        :return:
        """
        return sum(self.vp['utility'].a)

    def compute_final_size(self):
        """
        Computes final size of an outbreak
        :return:
        """
        self.set_vertex_filter(self.vp['recovered'])
        num_infected = self.num_vertices()
        self.clear_filters()
        return num_infected

    def compute_relative_size(self):
        """
        Computes relative final size of graph
        :return:
        """
        return self.compute_final_size() / self.num_vertices()

    def expected_nb_infections(self):
        """
        Computes the expected number of infections in the network
        :return:
        """
        return sum(self.vp['attack_decision'].a * (1 - self.vp['security'].a))

    def compute_centrality(self, display=False):
        """

        :param display:
        :return:
        """
        return 0