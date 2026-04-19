import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
from enum import Enum


class SafetyLevel(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class LaneType(Enum):
    NORMAL = "NORMAL"
    NARROW = "NARROW"
    INTERSECTION = "INTERSECTION"
    HUMAN_ZONE = "HUMAN_ZONE"


class LaneGraph:
    def __init__(self):
        self.graph = nx.DiGraph()
        self.nodes = {}
        self.edges = {}
    
    def add_node(self, node_id, x, y):
        """Add a node with position coordinates."""
        self.graph.add_node(node_id, x=x, y=y)
        self.nodes[node_id] = (x, y)
    
    def add_lane(self, u, v, max_speed, safety_level, lane_type, bidirectional=False, capacity=2):
        """Add a lane (edge) with metadata."""
        edge_attrs = {
            'max_speed': max_speed,
            'safety_level': safety_level,
            'lane_type': lane_type,
            'capacity': capacity,
            'congestion_score': 0.0,
            'historical_usage_count': 0
        }
        
        self.graph.add_edge(u, v, **edge_attrs)
        self.edges[(u, v)] = edge_attrs
        
        if bidirectional:
            self.graph.add_edge(v, u, **edge_attrs)
            self.edges[(v, u)] = edge_attrs.copy()
    
    def get_lane_metadata(self, u, v):
        """Get all metadata for a lane."""
        if self.graph.has_edge(u, v):
            return dict(self.graph[u][v])
        return None
    
    def update_congestion(self, u, v, score):
        """Update congestion score for a lane."""
        if self.graph.has_edge(u, v):
            self.graph[u][v]['congestion_score'] = score
    
    def is_lane_critical(self, u, v):
        """Check if a lane has critical safety level."""
        if self.graph.has_edge(u, v):
            return self.graph[u][v]['safety_level'] == SafetyLevel.CRITICAL
        return False
    
    def get_routing_weight(self, u, v):
        """Calculate routing weight for a lane."""
        if not self.graph.has_edge(u, v):
            return float('inf')
        
        edge_data = self.graph[u][v]
        congestion = edge_data.get('congestion_score', 0.0)
        max_speed = edge_data.get('max_speed', 1.0)
        lane_type = edge_data.get('lane_type')
        
        weight = (1 + congestion * 3) / max_speed
        
        if lane_type in [LaneType.NARROW, LaneType.HUMAN_ZONE]:
            weight *= 2.0
        elif lane_type == LaneType.INTERSECTION:
            weight *= 1.5
        
        return weight
    
    def get_node_position(self, node_id):
        """Get (x, y) position of a node."""
        if node_id in self.graph.nodes:
            return (self.graph.nodes[node_id]['x'], self.graph.nodes[node_id]['y'])
        return None
    
    def get_all_nodes(self):
        """Get list of all node IDs."""
        return list(self.graph.nodes())
    
    def get_all_edges(self):
        """Get list of all edges as (u, v) tuples."""
        return list(self.graph.edges())
    
    def export_heatmap_image(self, filename="heatmap.png"):
        """Export lane usage heatmap as an image."""
        fig, ax = plt.subplots(figsize=(12, 10))
        
        # Get node positions
        positions = {}
        for node in self.graph.nodes():
            positions[node] = self.get_node_position(node)
        
        # Draw nodes
        x_coords = [pos[0] for pos in positions.values()]
        y_coords = [pos[1] for pos in positions.values()]
        ax.scatter(x_coords, y_coords, c='blue', s=200, zorder=3, alpha=0.6)
        
        # Add node labels
        for node, (x, y) in positions.items():
            ax.text(x, y, str(node), fontsize=8, ha='center', va='center', 
                   color='white', weight='bold', zorder=4)
        
        # Draw edges colored by historical usage
        edges = self.get_all_edges()
        if edges:
            usage_counts = []
            for u, v in edges:
                usage = self.graph[u][v].get('historical_usage_count', 0)
                usage_counts.append(usage)
            
            # Normalize usage counts for color mapping
            max_usage = max(usage_counts) if usage_counts else 1
            max_usage = max(max_usage, 1)
            
            # Draw edges
            for (u, v), usage in zip(edges, usage_counts):
                x1, y1 = positions[u]
                x2, y2 = positions[v]
                
                # Normalize color (0 to 1)
                color_intensity = usage / max_usage
                
                ax.plot([x1, x2], [y1, y2], 
                       color=plt.cm.hot(color_intensity),
                       linewidth=2, alpha=0.7, zorder=1)
            
            # Add colorbar
            sm = plt.cm.ScalarMappable(cmap='hot', 
                                      norm=plt.Normalize(vmin=0, vmax=max_usage))
            sm.set_array([])
            cbar = plt.colorbar(sm, ax=ax)
            cbar.set_label('Historical Usage Count', rotation=270, labelpad=20)
        
        ax.set_xlabel('X Position')
        ax.set_ylabel('Y Position')
        ax.set_title('Lane Usage Heatmap', fontsize=16, weight='bold')
        ax.grid(True, alpha=0.3)
        ax.set_aspect('equal')
        
        plt.tight_layout()
        plt.savefig(filename, dpi=150, bbox_inches='tight')
        plt.close(fig)
    
    def generate_warehouse_map(self):
        """Generate a warehouse map with 20 nodes in a grid pattern."""
        # Row 1: Top row (loading docks) - y=80
        self.add_node(0, 100, 80)
        self.add_node(1, 300, 80)
        self.add_node(2, 600, 80)
        self.add_node(3, 900, 80)
        
        # Row 2: Second row - y=220
        self.add_node(4, 100, 220)
        self.add_node(5, 300, 220)
        self.add_node(6, 600, 220)
        self.add_node(7, 900, 220)
        
        # Row 3: Middle row (intersections) - y=360
        self.add_node(8, 100, 360)
        self.add_node(9, 300, 360)
        self.add_node(10, 600, 360)
        self.add_node(11, 900, 360)
        
        # Row 4: Fourth row - y=500
        self.add_node(12, 100, 500)
        self.add_node(13, 300, 500)
        self.add_node(14, 600, 500)
        self.add_node(15, 900, 500)
        
        # Row 5: Bottom row (storage) - y=640
        self.add_node(16, 100, 640)
        self.add_node(17, 300, 640)
        self.add_node(18, 600, 640)
        self.add_node(19, 900, 640)
        
        # Add lanes - Row 1 (Human zones - loading docks)
        self.add_lane(0, 1, 1.5, SafetyLevel.HIGH, LaneType.HUMAN_ZONE, bidirectional=True, capacity=2)
        self.add_lane(1, 2, 1.5, SafetyLevel.HIGH, LaneType.HUMAN_ZONE, bidirectional=True, capacity=2)
        self.add_lane(2, 3, 1.5, SafetyLevel.HIGH, LaneType.HUMAN_ZONE, bidirectional=True, capacity=2)
        
        # Add lanes - Row 2 (Main corridors)
        self.add_lane(4, 5, 4.0, SafetyLevel.LOW, LaneType.NORMAL, bidirectional=True, capacity=2)
        self.add_lane(5, 6, 4.0, SafetyLevel.CRITICAL, LaneType.NORMAL, bidirectional=True, capacity=2)
        self.add_lane(6, 7, 4.0, SafetyLevel.LOW, LaneType.NORMAL, bidirectional=True, capacity=2)
        
        # Add lanes - Row 3 (Intersections)
        self.add_lane(8, 9, 2.0, SafetyLevel.CRITICAL, LaneType.INTERSECTION, bidirectional=True, capacity=2)
        self.add_lane(9, 10, 2.0, SafetyLevel.CRITICAL, LaneType.INTERSECTION, bidirectional=True, capacity=2)
        self.add_lane(10, 11, 2.0, SafetyLevel.CRITICAL, LaneType.INTERSECTION, bidirectional=True, capacity=2)
        
        # Add lanes - Row 4 (Normal corridors)
        self.add_lane(12, 13, 3.0, SafetyLevel.MEDIUM, LaneType.NORMAL, bidirectional=True, capacity=2)
        self.add_lane(13, 14, 3.0, SafetyLevel.MEDIUM, LaneType.NORMAL, bidirectional=True, capacity=2)
        self.add_lane(14, 15, 3.0, SafetyLevel.MEDIUM, LaneType.NORMAL, bidirectional=True, capacity=2)
        
        # Add lanes - Row 5 (Narrow storage aisles)
        self.add_lane(16, 17, 1.0, SafetyLevel.MEDIUM, LaneType.NARROW, bidirectional=True, capacity=2)
        self.add_lane(17, 18, 1.0, SafetyLevel.MEDIUM, LaneType.NARROW, bidirectional=True, capacity=2)
        self.add_lane(18, 19, 1.0, SafetyLevel.MEDIUM, LaneType.NARROW, bidirectional=True, capacity=2)
        
        # Vertical connections (Column 1 - leftmost)
        self.add_lane(0, 4, 3.0, SafetyLevel.LOW, LaneType.NORMAL, bidirectional=False, capacity=2)
        self.add_lane(4, 8, 3.0, SafetyLevel.MEDIUM, LaneType.NORMAL, bidirectional=False, capacity=2)
        self.add_lane(8, 12, 2.5, SafetyLevel.MEDIUM, LaneType.NORMAL, bidirectional=False, capacity=2)
        self.add_lane(12, 16, 1.0, SafetyLevel.MEDIUM, LaneType.NARROW, bidirectional=False, capacity=2)
        
        # Vertical connections (Column 2)
        self.add_lane(1, 5, 3.0, SafetyLevel.LOW, LaneType.NORMAL, bidirectional=False, capacity=2)
        self.add_lane(5, 9, 2.0, SafetyLevel.HIGH, LaneType.INTERSECTION, bidirectional=False, capacity=2)
        self.add_lane(9, 13, 2.5, SafetyLevel.MEDIUM, LaneType.NORMAL, bidirectional=False, capacity=2)
        self.add_lane(13, 17, 1.0, SafetyLevel.MEDIUM, LaneType.NARROW, bidirectional=False, capacity=2)
        
        # Vertical connections (Column 3)
        self.add_lane(2, 6, 3.0, SafetyLevel.LOW, LaneType.NORMAL, bidirectional=False, capacity=2)
        self.add_lane(6, 10, 2.0, SafetyLevel.HIGH, LaneType.INTERSECTION, bidirectional=False, capacity=2)
        self.add_lane(10, 14, 2.5, SafetyLevel.MEDIUM, LaneType.NORMAL, bidirectional=False, capacity=2)
        self.add_lane(14, 18, 1.0, SafetyLevel.MEDIUM, LaneType.NARROW, bidirectional=False, capacity=2)
        
        # Vertical connections (Column 4 - rightmost)
        self.add_lane(3, 7, 3.0, SafetyLevel.LOW, LaneType.NORMAL, bidirectional=False, capacity=2)
        self.add_lane(7, 11, 2.0, SafetyLevel.HIGH, LaneType.INTERSECTION, bidirectional=False, capacity=2)
        self.add_lane(11, 15, 2.5, SafetyLevel.MEDIUM, LaneType.NORMAL, bidirectional=False, capacity=2)
        self.add_lane(15, 19, 1.0, SafetyLevel.MEDIUM, LaneType.NARROW, bidirectional=False, capacity=2)
        
        # Add some reverse vertical connections for variety
        self.add_lane(16, 12, 2.0, SafetyLevel.MEDIUM, LaneType.NORMAL, bidirectional=False, capacity=2)
        self.add_lane(17, 13, 2.0, SafetyLevel.MEDIUM, LaneType.NORMAL, bidirectional=False, capacity=2)
        self.add_lane(18, 14, 2.0, SafetyLevel.MEDIUM, LaneType.NORMAL, bidirectional=False, capacity=2)
        self.add_lane(19, 15, 2.0, SafetyLevel.MEDIUM, LaneType.NORMAL, bidirectional=False, capacity=2)
        
        return self


if __name__ == "__main__":
    lg = LaneGraph()
    graph = lg.generate_warehouse_map()
    print(f"Nodes: {len(graph.get_all_nodes())}")
    print(f"Edges: {len(graph.get_all_edges())}")
    print(f"Sample lane metadata: {graph.get_lane_metadata(0, 4)}")
    graph.export_heatmap_image("test_heatmap.png")
    print("Heatmap saved")
