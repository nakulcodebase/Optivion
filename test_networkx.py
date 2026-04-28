import osmnx as ox
import networkx as nx

print("Testing simple OSMnx download...")
try:
    # A tiny 2km box in Mumbai
    G = ox.graph_from_point((19.0760, 72.8777), dist=2000, network_type='drive')
    print("Graph downloaded. Nodes:", len(G.nodes))
    
    # Random nodes
    o_node = list(G.nodes)[0]
    d_node = list(G.nodes)[-1]
    
    path = nx.astar_path(G, o_node, d_node, weight='length')
    print("Path found. Length:", len(path))
    
except Exception as e:
    print("Error:", e)
