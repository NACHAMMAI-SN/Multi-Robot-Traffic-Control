import numpy as np
from math import log1p


class LaneHeatmap:
    def __init__(self, lane_graph):
        """Initialize lane heatmap with usage tracking."""
        self.lane_graph = lane_graph
        edges = lane_graph.get_all_edges()
        self.usage_count = {(u, v): 0 for u, v in edges}
        self.real_time_occupancy = {(u, v): 0 for u, v in edges}
        self.step_history = []
    
    def record_traversal(self, u, v):
        """Record a lane traversal and update congestion."""
        key = (u, v)
        if key not in self.usage_count:
            self.usage_count[key] = 0
        self.usage_count[key] += 1
        
        meta = self.lane_graph.get_lane_metadata(u, v)
        if not meta:
            return
        
        capacity = meta.get('capacity', 2)
        occupancy = self.real_time_occupancy.get(key, 0)
        congestion = min(1.0, occupancy / max(capacity, 1) +
                        0.05 * log1p(self.usage_count[key]) / 10)
        
        self.lane_graph.update_congestion(u, v, congestion)
        self.lane_graph.graph[u][v]['historical_usage_count'] = self.usage_count[key]
    
    def set_occupancy(self, u, v, count):
        """Set real-time occupancy for a lane."""
        key = (u, v)
        self.real_time_occupancy[key] = max(0, count)
        
        meta = self.lane_graph.get_lane_metadata(u, v)
        if not meta:
            return
        
        capacity = meta.get('capacity', 2)
        congestion = min(1.0, count / max(capacity, 1) +
                        0.05 * log1p(self.usage_count.get(key, 0)) / 10)
        self.lane_graph.update_congestion(u, v, congestion)
    
    def get_congestion_hotspots(self):
        """Get top 5 most congested lanes."""
        scores = []
        for u, v in self.lane_graph.get_all_edges():
            meta = self.lane_graph.get_lane_metadata(u, v)
            if meta:
                scores.append((u, v, meta.get('congestion_score', 0.0)))
        scores.sort(key=lambda x: x[2], reverse=True)
        return scores[:5]
    
    def get_heatmap_color(self, u, v):
        """Get RGB color tuple for a lane based on congestion."""
        meta = self.lane_graph.get_lane_metadata(u, v)
        c = meta.get('congestion_score', 0.0) if meta else 0.0
        
        if c < 0.3:
            t = c / 0.3
            return (int(t * 255), int(255 - t * 35), int(100 - t * 100))
        elif c < 0.7:
            t = (c - 0.3) / 0.4
            return (255, int(220 - t * 80), 0)
        else:
            t = (c - 0.7) / 0.3
            return (255, int(140 - t * 100), 0)
    
    def get_heatmap_matrix(self):
        """Get congestion matrix as numpy array."""
        nodes = self.lane_graph.get_all_nodes()
        n = len(nodes)
        idx = {node: i for i, node in enumerate(nodes)}
        matrix = np.zeros((n, n))
        
        for u, v in self.lane_graph.get_all_edges():
            meta = self.lane_graph.get_lane_metadata(u, v)
            if meta:
                matrix[idx[u]][idx[v]] = meta.get('congestion_score', 0.0)
        
        return matrix
    
    def get_routing_weight(self, u, v):
        """Get routing weight with congestion penalty."""
        base = self.lane_graph.get_routing_weight(u, v)
        meta = self.lane_graph.get_lane_metadata(u, v)
        c = meta.get('congestion_score', 0.0) if meta else 0.0
        return base * (1 + c * 2)
    
    def snapshot(self, step):
        """Take a snapshot of congestion state."""
        if step % 10 == 0:
            self.step_history.append({
                "step": step,
                "hotspots": self.get_congestion_hotspots()
            })
        if len(self.step_history) > 50:
            self.step_history = self.step_history[-50:]
    
    def export_stats(self):
        """Export heatmap statistics."""
        return {
            "total_traversals": sum(self.usage_count.values()),
            "hotspots": self.get_congestion_hotspots(),
            "step_history": self.step_history[-10:]
        }
