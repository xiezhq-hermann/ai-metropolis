import sys
import json
import math
from collections import defaultdict, deque

from .tokens import count_tokens

VISION_RADIUS = 4


def init_graph(movements, base_step, target_step):

    persona_list = list(movements.keys())
    dependency_dag = {}
    dependency_reverse_dag = {}

    for step in range(base_step, target_step):
        for persona in persona_list:
            id = f"{persona}:{step}"
            assert id not in dependency_dag
            assert id not in dependency_reverse_dag
            dependency_dag[id] = []
            dependency_reverse_dag[id] = []

            while f"{persona}:{step-1}" not in dependency_dag and step > base_step:
                step -= 1
            if step > base_step:
                dependency_dag[f"{persona}:{step-1}"].append(id)
                dependency_reverse_dag[id].append(f"{persona}:{step-1}")
    return dependency_dag, dependency_reverse_dag


def clustering(step, movements):
    personas = set(movements.keys())
    clusters = []
    visited = set()

    for p in personas:
        if p in visited:
            continue

        cluster = []
        queue = [p]
        while len(queue) > 0:
            persona = queue.pop(0)
            if persona in visited:
                continue

            visited.add(persona)
            cluster.append(persona)
            x, y = movements[persona][step]
            for _p in personas:
                if _p in visited:
                    continue
                _x, _y = movements[_p][step]
                dist = math.sqrt((x - _x)**2 + (y - _y)**2)
                if dist <= VISION_RADIUS:
                    queue.append(_p)
        clusters.append(cluster)
    assert len(personas) == sum([len(c) for c in clusters])
    return clusters


def add_persona_dependency(cluster, step, dependency_dag, dependency_reverse_dag):

    for p in cluster:
        id = f"{p}:{step}"
        for coupled_p in cluster:
            if coupled_p == p:
                continue
            coupled_id = f"{coupled_p}:{step}"
            for d in dependency_reverse_dag[coupled_id]:
                assert d in dependency_dag
                if id not in dependency_dag[d]:
                    assert d not in dependency_reverse_dag[id]
                    dependency_dag[d].append(id)
                    dependency_reverse_dag[id].append(d)

            for d in dependency_dag[id]:
                assert d in dependency_reverse_dag
                if coupled_id not in dependency_reverse_dag[d]:
                    assert d not in dependency_dag[coupled_id]
                    dependency_reverse_dag[d].append(coupled_id)
                    dependency_dag[coupled_id].append(d)


def build_dependency_graph(movements, base_step, target_step):
    dependency_dag, dependency_reverse_dag = init_graph(movements, base_step, target_step)

    for s in range(base_step, target_step):
        clusters = clustering(s, movements)
        for cluster in clusters:
            if len(cluster) == 1:
                continue
            add_persona_dependency(cluster, s, dependency_dag, dependency_reverse_dag)
    return dependency_dag, dependency_reverse_dag


def topological_sort(graph, in_degree):
    # Kahn's Algorithm for Topological Sorting
    zero_in_degree_queue = deque([node for node in graph if in_degree[node] == 0])
    topo_order = []

    while zero_in_degree_queue:
        current_node = zero_in_degree_queue.popleft()
        topo_order.append(current_node)

        for neighbor in graph[current_node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                zero_in_degree_queue.append(neighbor)

    if len(topo_order) == len(graph):
        return topo_order
    else:
        return []  # Graph has a cycle


def get_factor(node, traces):
    factor = 0
    persona, step = node.split(":")
    if step in traces and persona in traces[step]:
        for call in traces[step][persona]:
            factor += count_tokens(call["prompt"]) + count_tokens(call["reference_output"])
    return factor


def find_critical_path(dag_dependency, traces):
    graph = defaultdict(list)
    node_factors = {}
    in_degree = defaultdict(int)

    # Parse JSON data
    for node in dag_dependency:
        node_factors[node] = get_factor(node, traces)
        for neighbor in dag_dependency[node]:
            graph[node].append(neighbor)
            in_degree[neighbor] += 1

    # Add nodes with no outgoing edges
    for node in node_factors:
        if node not in graph:
            graph[node] = []

    # Topological Sort
    topo_order = topological_sort(graph, in_degree)

    if not topo_order:
        return "The graph has a cycle, and no topological ordering exists."

    # Initialize DP table
    max_sum = {node: float('-inf') for node in node_factors}
    predecessor = {node: None for node in node_factors}

    # Set the sum of the starting nodes to their factor values
    for node in topo_order:
        if in_degree[node] == 0:
            max_sum[node] = node_factors[node]

    print(f"the sum of factors: {sum([node_factors[node] for node in node_factors])}")

    # DP to calculate the max sum path
    for node in topo_order:
        for neighbor in graph[node]:
            if max_sum[neighbor] < max_sum[node] + node_factors[neighbor]:
                max_sum[neighbor] = max_sum[node] + node_factors[neighbor]
                predecessor[neighbor] = node

    # Find the end node of the max sum path
    end_node = max(max_sum, key=max_sum.get)
    max_path_sum = max_sum[end_node]

    # Reconstruct the path
    critical_path = []
    while end_node is not None:
        critical_path.append(end_node)
        end_node = predecessor[end_node]

    critical_path.reverse()
    return critical_path


if __name__ == "__main__":
    if (len(sys.argv) < 2):
        print("Usage: python parse_traces.py <traces_file> <movement>")
        sys.exit(1)

    base_step = 2880
    target_step = 3060

    traces = json.load(open(sys.argv[1]))
    movements = json.load(open(sys.argv[2]))

    dependency_dag, dependency_reverse_dag = build_dependency_graph(movements=movements,
                                                                    base_step=base_step,
                                                                    target_step=target_step)
    critical_path = find_critical_path(dag_dependency=dependency_dag, traces=traces)
    json.dump(dependency_dag, open("dependency_dag.json", "w"))
    json.dump(dependency_reverse_dag, open("dependency_reverse_dag.json", "w"))
    json.dump(critical_path, open("critical_path.json", "w"))
