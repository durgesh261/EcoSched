"""
Distributed cluster topology, heterogeneous node manager, and inter-region WAN latency matrix.
"""

from typing import Dict, List, Optional, Tuple
from .models import Region, NodeSpec
from .node import ComputeNode


class DistributedCluster:
    """
    Coordinates a multi-region heterogeneous cluster.
    Models WAN bandwidth, cross-region data transfer latency, and datacenter PUE differences.
    """

    def __init__(self):
        self.nodes: Dict[str, ComputeNode] = {}
        self.nodes_by_region: Dict[Region, List[ComputeNode]] = {r: [] for r in Region}

        # Inter-region network bandwidth (Gbps) and RTT (ms) matrix
        # (src, dst) -> (RTT_ms, Bandwidth_Gbps)
        self.network_matrix: Dict[Tuple[Region, Region], Tuple[float, float]] = {
            # Local
            (Region.DE, Region.DE): (1.0, 100.0),
            (Region.SE, Region.SE): (1.0, 100.0),
            (Region.US_CA, Region.US_CA): (1.0, 100.0),
            (Region.FR, Region.FR): (1.0, 100.0),

            # European cross-region
            (Region.DE, Region.FR): (15.0, 20.0),
            (Region.FR, Region.DE): (15.0, 20.0),
            (Region.DE, Region.SE): (25.0, 15.0),
            (Region.SE, Region.DE): (25.0, 15.0),
            (Region.FR, Region.SE): (30.0, 15.0),
            (Region.SE, Region.FR): (30.0, 15.0),

            # Transatlantic / Intercontinental
            (Region.DE, Region.US_CA): (140.0, 5.0),
            (Region.US_CA, Region.DE): (140.0, 5.0),
            (Region.FR, Region.US_CA): (135.0, 5.0),
            (Region.US_CA, Region.FR): (135.0, 5.0),
            (Region.SE, Region.US_CA): (150.0, 4.0),
            (Region.US_CA, Region.SE): (150.0, 4.0),
        }

    def add_node(self, spec: NodeSpec) -> ComputeNode:
        """Adds a compute node to the cluster."""
        node = ComputeNode(spec)
        self.nodes[node.node_id] = node
        self.nodes_by_region[spec.region].append(node)
        return node

    def compute_transfer_delay_min(self, src_region: Region, dest_region: Region, data_size_gb: float) -> float:
        """
        Calculates network transfer delay in minutes:
        Delay = RTT + (DataSize_GB * 8) / (Bandwidth_Gbps)
        """
        if src_region == dest_region or data_size_gb <= 0:
            return 0.0

        pair = (src_region, dest_region)
        rtt_ms, bw_gbps = self.network_matrix.get(pair, (150.0, 5.0))

        # Transfer time in seconds
        rtt_sec = rtt_ms / 1000.0
        data_transfer_sec = (data_size_gb * 8.0) / bw_gbps
        total_delay_sec = rtt_sec + data_transfer_sec
        return total_delay_sec / 60.0

    def get_candidate_nodes(self, cpu: int, ram: int, gpu: int, target_region: Optional[Region] = None) -> List[ComputeNode]:
        """Returns all nodes that can currently fit the resource requirements."""
        if target_region:
            pool = self.nodes_by_region[target_region]
        else:
            pool = list(self.nodes.values())

        return [n for n in pool if n.can_accommodate(cpu, ram, gpu)]

    def get_total_capacity(self) -> Dict[str, int]:
        """Returns total compute capacities across cluster."""
        return {
            "total_nodes": len(self.nodes),
            "total_cpu": sum(n.total_cpu for n in self.nodes.values()),
            "total_ram_gb": sum(n.total_ram for n in self.nodes.values()),
            "total_gpu": sum(n.total_gpu for n in self.nodes.values())
        }

    def reset(self):
        """Resets all node states."""
        for node in self.nodes.values():
            node.reset_metrics()

    @classmethod
    def create_default_heterogeneous_cluster(cls) -> "DistributedCluster":
        """
        Builds a standard 4-region heterogeneous research cluster:
        - Germany (DE): 6 general CPU nodes + 2 GPU AI nodes (PUE=1.22)
        - Sweden (SE): 6 general CPU nodes + 2 GPU AI nodes (PUE=1.12 - hydro cooled)
        - California (US_CA): 4 CPU nodes + 2 GPU AI nodes (PUE=1.25)
        - France (FR): 4 CPU nodes + 1 GPU node (PUE=1.18)
        Total: 27 nodes
        """
        cluster = cls()

        regions_config = [
            (Region.DE, 6, 2, 1.22),
            (Region.SE, 6, 2, 1.12),
            (Region.US_CA, 4, 2, 1.25),
            (Region.FR, 4, 1, 1.18),
        ]

        for region, num_cpu_nodes, num_gpu_nodes, pue in regions_config:
            # Standard CPU compute node
            for i in range(num_cpu_nodes):
                spec = NodeSpec(
                    node_id=f"node_{region.value.lower()}_cpu_{i:02d}",
                    region=region,
                    total_cpu_cores=64,
                    total_memory_gb=256,
                    total_gpu_units=0,
                    idle_power_watts=95.0,
                    peak_power_watts=380.0,
                    pue=pue
                )
                cluster.add_node(spec)

            # High-Performance GPU AI node
            for j in range(num_gpu_nodes):
                spec = NodeSpec(
                    node_id=f"node_{region.value.lower()}_gpu_{j:02d}",
                    region=region,
                    total_cpu_cores=96,
                    total_memory_gb=512,
                    total_gpu_units=4,
                    idle_power_watts=140.0,
                    peak_power_watts=480.0,
                    gpu_idle_watts=30.0,
                    gpu_peak_watts=350.0,
                    pue=pue
                )
                cluster.add_node(spec)

        return cluster
