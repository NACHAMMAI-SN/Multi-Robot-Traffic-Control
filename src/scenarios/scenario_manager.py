"""Scenario management with 3 unique operational modes."""


class ScenarioManager:
    """Manages different operational scenarios for the warehouse."""
    
    SCENARIOS = {
        "night_shift": {
            "name": "Night Shift",
            "emoji": "🌙",
            "robots": 8,
            "color": (80, 80, 160),
            "description": "Reduced capacity, maintenance lanes closed",
            "max_steps": 800,
        },
        "peak_hours": {
            "name": "Peak Hours",
            "emoji": "⚡",
            "robots": 12,
            "color": (200, 140, 40),
            "description": "12 robots, maximum congestion stress test",
            "max_steps": 1000,
        },
        "emergency": {
            "name": "Emergency Evacuation",
            "emoji": "🚨",
            "robots": 10,
            "color": (200, 50, 50),
            "description": "Robots racing to safe zones with countdown!",
            "max_steps": 300,  # tight countdown!
        }
    }
    
    def apply(self, scenario_key, lane_graph, robots):
        """Apply scenario modifications to lane graph and robots."""
        if scenario_key == "night_shift":
            self._night_shift(lane_graph, robots)
        elif scenario_key == "peak_hours":
            self._peak_hours(lane_graph, robots)
        elif scenario_key == "emergency":
            self._emergency(lane_graph, robots)
    
    def _night_shift(self, lane_graph, robots):
        """Night shift: reduced capacity, maintenance lanes closed."""
        # Close 4 maintenance lanes - mark with enormous weight
        all_edges = lane_graph.get_all_edges()
        maintenance = all_edges[5:9] if len(all_edges) >= 9 else all_edges[:4]
        for u, v in maintenance:
            lane_graph.graph[u][v]['closed'] = True
            lane_graph.graph[u][v]['weight'] = 99999
            lane_graph.graph[u][v]['congestion_score'] = 1.0
        
        # Reduce all speeds by 30%
        for u, v in lane_graph.get_all_edges():
            lane_graph.graph[u][v]['max_speed'] = max(
                0.5, lane_graph.graph[u][v].get('max_speed', 3.0) * 0.7)
        
        # All human zones become CRITICAL
        from src.map.lane_graph import LaneType, SafetyLevel
        for u, v in lane_graph.get_all_edges():
            meta = lane_graph.get_lane_metadata(u, v)
            if meta and meta.get('lane_type') == LaneType.HUMAN_ZONE:
                lane_graph.graph[u][v]['safety_level'] = SafetyLevel.CRITICAL
    
    def _peak_hours(self, lane_graph, robots):
        """Peak hours: 12 robots, pre-congested lanes."""
        # Pre-congest all lanes
        for u, v in lane_graph.get_all_edges():
            lane_graph.update_congestion(u, v, 0.35)
        
        # Intersections single capacity
        from src.map.lane_graph import LaneType
        for u, v in lane_graph.get_all_edges():
            meta = lane_graph.get_lane_metadata(u, v)
            if meta and meta.get('lane_type') == LaneType.INTERSECTION:
                lane_graph.graph[u][v]['capacity'] = 1
    
    def _emergency(self, lane_graph, robots):
        """Emergency evacuation: all robots rush to safe zones."""
        # Safe zones = nodes 16,17,18,19
        safe_zones = [16, 17, 18, 19]
        for i, robot in enumerate(robots):
            robot.goal_node = safe_zones[i % len(safe_zones)]
            robot.path = []
            robot.path_index = 0
            robot.compute_path()
        
        # Boost main corridor speeds
        from src.map.lane_graph import LaneType
        for u, v in lane_graph.get_all_edges():
            meta = lane_graph.get_lane_metadata(u, v)
            if meta and meta.get('lane_type') and \
               meta['lane_type'].name == 'NORMAL':
                lane_graph.graph[u][v]['max_speed'] = min(
                    8.0,
                    lane_graph.graph[u][v].get('max_speed', 3.0) * 1.5)
