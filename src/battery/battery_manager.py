"""Battery management system for robots."""


class BatteryManager:
    """Manages battery levels and charging for all robots."""
    
    def __init__(self, robots):
        self.batteries = {r.id: 100.0 for r in robots}
        self.charging_stations = [3, 7, 11, 15]
        self.drain_rates = {
            "MOVING": 0.8,
            "WAITING": 0.2,
            "EMERGENCY_STOP": 0.1,
            "IDLE": 0.05,
            "GOAL_REACHED": 0.0,
        }
        self.low_threshold = 25.0
        self.critical_threshold = 10.0
        self.dead_threshold = 2.0
        self.charging_robots = set()
    
    def update(self, robot, step) -> float:
        """Update battery level for a robot based on activity."""
        bat = self.batteries[robot.id]
        
        # Charging at station
        if robot.current_node in self.charging_stations:
            self.charging_robots.add(robot.id)
            bat = min(100.0, bat + 5.0)  # charge 5% per step
        else:
            if robot.id in self.charging_robots:
                self.charging_robots.discard(robot.id)
            
            # Normal drain based on status
            rate = self.drain_rates.get(robot.status.name, 0.1)
            
            # Extra drain on difficult lanes
            lane = robot.get_current_lane()
            if lane:
                meta = robot.lane_graph.get_lane_metadata(*lane)
                if meta:
                    lt = meta.get('lane_type')
                    if lt and lt.name in ('NARROW', 'HUMAN_ZONE'):
                        rate *= 1.5
            
            bat = max(0.0, bat - rate)
        
        self.batteries[robot.id] = bat
        return bat
    
    def needs_charging(self, robot_id) -> bool:
        """Check if robot needs charging (below critical threshold)."""
        return self.batteries[robot_id] <= self.critical_threshold
    
    def is_dead(self, robot_id) -> bool:
        """Check if robot battery is dead."""
        return self.batteries[robot_id] <= self.dead_threshold
    
    def is_charging(self, robot_id) -> bool:
        """Check if robot is currently charging."""
        return robot_id in self.charging_robots
    
    def is_at_charger(self, robot) -> bool:
        """Check if robot is at a charging station."""
        return robot.current_node in self.charging_stations
    
    def get_nearest_charger(self, robot) -> int:
        """Find nearest charging station to robot."""
        curr = robot.current_node
        try:
            import networkx as nx
            distances = {}
            for cs in self.charging_stations:
                try:
                    path = nx.astar_path(robot.lane_graph.graph, curr, cs)
                    distances[cs] = len(path)
                except:
                    distances[cs] = 9999
            return min(distances, key=distances.get)
        except:
            return min(self.charging_stations, key=lambda c: abs(c - curr))
    
    def get_battery_color(self, robot_id) -> tuple:
        """Get color for battery level indicator."""
        bat = self.batteries[robot_id]
        if bat > 50: return (80, 220, 120)  # Green
        if bat > 25: return (255, 200, 60)  # Yellow
        if bat > 10: return (255, 130, 30)  # Orange
        return (255, 60, 60)  # Red
    
    def get_status(self, robot_id) -> str:
        """Get battery status string."""
        bat = self.batteries[robot_id]
        if robot_id in self.charging_robots: return "CHARGING"
        if bat <= self.dead_threshold:        return "DEAD"
        if bat <= self.critical_threshold:    return "CRITICAL"
        if bat <= self.low_threshold:         return "LOW"
        return "OK"
    
    def export_stats(self) -> dict:
        """Export battery statistics."""
        return {
            "final_batteries": self.batteries,
            "charging_stations": self.charging_stations,
            "robots_that_charged": list(self.charging_robots)
        }
