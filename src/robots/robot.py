from enum import Enum
import networkx as nx


class RobotStatus(Enum):
    IDLE = "IDLE"
    MOVING = "MOVING"
    WAITING = "WAITING"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    GOAL_REACHED = "GOAL_REACHED"


class Robot:
    def __init__(self, robot_id, start_node, goal_node, lane_graph, color=(255, 255, 255)):
        self.id = robot_id
        self.current_node = start_node
        self.goal_node = goal_node
        self.lane_graph = lane_graph
        self.color = color
        self.status = RobotStatus.IDLE
        self.current_speed = 0.0
        self.base_speed = 3.0
        self.path = []
        self.path_index = 0
        self.move_progress = 0.0
        self.trajectory_log = []
        self.waiting_for = None
        self.reserved_lanes = set()
        self.emergency_flash_timer = 0
        self.replan_count = 0
        self.steps_waiting = 0
        self.goal_reached_step = None
        self.start_delay = 0  # Staggered start delay
    
    def compute_path(self, avoid_nodes=None):
        """Compute path from current node to goal using A* algorithm."""
        try:
            # Create subgraph if we need to avoid nodes
            graph = self.lane_graph.graph
            if avoid_nodes:
                nodes_to_keep = set(graph.nodes()) - set(avoid_nodes)
                graph = graph.subgraph(nodes_to_keep)
            
            # Define weight function
            def weight_func(u, v, d):
                return self.lane_graph.get_routing_weight(u, v)
            
            # Define heuristic function (euclidean distance)
            def heuristic(node1, node2):
                pos1 = self.lane_graph.get_node_position(node1)
                pos2 = self.lane_graph.get_node_position(node2)
                if pos1 is None or pos2 is None:
                    return 0
                dx = pos2[0] - pos1[0]
                dy = pos2[1] - pos1[1]
                return (dx * dx + dy * dy) ** 0.5
            
            # Compute path
            path = nx.astar_path(
                graph,
                self.current_node,
                self.goal_node,
                heuristic=heuristic,
                weight=weight_func
            )
            
            self.path = path
            self.path_index = 0
            return True
            
        except (nx.NetworkXNoPath, nx.NodeNotFound, Exception) as e:
            self.status = RobotStatus.WAITING
            return False
    
    def get_current_lane(self):
        """Get current lane as (u, v) tuple."""
        if self.path_index < len(self.path) - 1:
            return (self.path[self.path_index], self.path[self.path_index + 1])
        return None
    
    def get_next_node(self):
        """Get next node in path."""
        if self.path_index + 1 < len(self.path):
            return self.path[self.path_index + 1]
        return None
    
    def adapt_speed(self, lane_metadata):
        """Adapt speed based on lane conditions."""
        from src.map.lane_graph import LaneType
        
        speed = self.base_speed
        congestion = lane_metadata.get('congestion_score', 0.0)
        max_speed = lane_metadata.get('max_speed', self.base_speed)
        lane_type = lane_metadata.get('lane_type')
        
        # Adjust for congestion
        if congestion > 0.7:
            speed *= 0.3
        elif congestion > 0.5:
            speed *= 0.5
        elif congestion > 0.3:
            speed *= 0.75
        
        # Adjust for lane type
        if lane_type == LaneType.NARROW:
            speed *= 0.6
        elif lane_type == LaneType.HUMAN_ZONE:
            speed *= 0.4
        elif lane_type == LaneType.INTERSECTION:
            speed *= 0.7
        
        return min(speed, max_speed)
    
    def emergency_stop(self):
        """Trigger emergency stop."""
        self.status = RobotStatus.EMERGENCY_STOP
        self.current_speed = 0.0
        # Shorter timer for faster recovery
        self.emergency_flash_timer = 30
    
    def check_safe_distance(self, all_robots):
        """Check if safe to move to next node. Ignores robots that reached their goal."""
        next_node = self.get_next_node()
        if next_node is None:
            return True
        
        for robot in all_robots:
            if robot.id != self.id and robot.current_node == next_node:
                # Ignore robots that have reached their goal
                if robot.status != RobotStatus.GOAL_REACHED:
                    return False
        
        return True
    
    def move_step(self, all_robots, traffic_controller, heatmap, step):
        """Execute one movement step. Returns status string."""
        
        # If already at goal
        if self.status == RobotStatus.GOAL_REACHED:
            return "goal"
        
        # Handle staggered start delay
        if self.start_delay > 0:
            self.start_delay -= 1
            return "waiting"
        
        # Handle emergency flash timer
        if self.emergency_flash_timer > 0:
            self.emergency_flash_timer -= 1
            if self.emergency_flash_timer == 0 and self.status == RobotStatus.EMERGENCY_STOP:
                # Replan with avoiding currently occupied nodes
                occupied = [r.current_node for r in all_robots 
                           if r.id != self.id and r.status != RobotStatus.GOAL_REACHED]
                self.replan_path(avoid_nodes=occupied if len(occupied) < 15 else None)
                self.status = RobotStatus.IDLE
                self.steps_waiting = 0
                return "waiting"  # Wait one step after replanning
        
        # Force replan if stuck waiting too long
        if self.steps_waiting > 15:
            # Try to avoid currently occupied nodes
            occupied = [r.current_node for r in all_robots 
                       if r.id != self.id and r.status != RobotStatus.GOAL_REACHED]
            self.replan_path(avoid_nodes=occupied if len(occupied) < 15 else None)
            self.steps_waiting = 0
            self.status = RobotStatus.IDLE
            return "waiting"
        
        # Check if we have a valid path
        if not self.path or self.path_index >= len(self.path) - 1:
            if not self.compute_path():
                self.steps_waiting += 1
                return "waiting"
        
        # Get next node
        next_node = self.get_next_node()
        if next_node is None:
            if self.current_node == self.goal_node:
                self.status = RobotStatus.GOAL_REACHED
                self.goal_reached_step = step
                return "goal"
            return "waiting"
        
        # Check safe distance
        if not self.check_safe_distance(all_robots):
            # Check if blocker is also stuck (mutual blockage)
            blocking_robot = None
            for robot in all_robots:
                if robot.id != self.id and robot.current_node == next_node:
                    blocking_robot = robot
                    break
            
            # If blocker is also waiting/stopped, just wait instead of emergency stop
            if blocking_robot and blocking_robot.status in (RobotStatus.WAITING, RobotStatus.EMERGENCY_STOP, RobotStatus.IDLE):
                self.status = RobotStatus.WAITING
                self.steps_waiting += 1
                return "waiting"
            else:
                # Only emergency stop if blocker is actively moving
                self.emergency_stop()
                self.steps_waiting += 1
                return "blocked"
        
        # Get lane metadata
        u, v = self.current_node, next_node
        
        # Check if critical lane needs reservation
        if self.lane_graph.is_lane_critical(u, v):
            granted = traffic_controller.reserve_lane(self.id, u, v)
            if not granted:
                self.status = RobotStatus.WAITING
                self.steps_waiting += 1
                self.waiting_for = traffic_controller.lane_reservations.get((u, v))
                return "waiting"
        
        # Get lane metadata and adapt speed
        lane_meta = self.lane_graph.get_lane_metadata(u, v)
        self.current_speed = self.adapt_speed(lane_meta)
        self.move_progress += self.current_speed * 0.15
        self.status = RobotStatus.MOVING
        self.waiting_for = None
        
        # Check if reached next node
        if self.move_progress >= 1.0:
            prev = self.current_node
            self.current_node = next_node
            self.path_index += 1
            self.move_progress = 0.0
            
            # Update heatmap and release lane
            heatmap.record_traversal(prev, self.current_node)
            traffic_controller.release_lane(self.id, prev, self.current_node)
            
            # Log trajectory
            self.trajectory_log.append({"node": self.current_node, "step": step})
            
            # Check if reached goal
            if self.current_node == self.goal_node:
                self.status = RobotStatus.GOAL_REACHED
                self.goal_reached_step = step
                return "goal"
            
            return "moved"
        
        return "moving"
    
    def replan_path(self, avoid_nodes=None):
        """Replan path with optional node avoidance."""
        self.replan_count += 1
        self.path = []
        self.path_index = 0
        self.move_progress = 0.0
        return self.compute_path(avoid_nodes)
    
    def get_pixel_position(self):
        """Get interpolated pixel position between current and next node."""
        curr = self.lane_graph.get_node_position(self.current_node)
        next_n = self.get_next_node()
        
        if next_n is None or self.move_progress == 0:
            return curr
        
        nxt = self.lane_graph.get_node_position(next_n)
        x = curr[0] + (nxt[0] - curr[0]) * self.move_progress
        y = curr[1] + (nxt[1] - curr[1]) * self.move_progress
        
        return (x, y)
    
    def get_trajectory(self):
        """Get complete trajectory log."""
        return self.trajectory_log


if __name__ == "__main__":
    from src.map.lane_graph import LaneGraph
    lg = LaneGraph()
    graph = lg.generate_warehouse_map()
    r = Robot("R0", 0, 19, graph)
    found = r.compute_path()
    print(f"Path found: {found}")
    print(f"Path: {r.path}")
    print(f"Next node: {r.get_next_node()}")
    print("Robot test PASSED")
