import networkx as nx
import osmnx as ox
import time

start = time.time()
G = ox.graph_from_place('Manhattan, New York, USA', network_type='drive')
print('Graph loaded in', time.time() - start)
