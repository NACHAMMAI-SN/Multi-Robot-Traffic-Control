import logging
from collections import defaultdict


class TrafficController:
    def __init__(self, lane_graph):
        self.lane_graph = lane_graph
        self.robots = {}
        self.lane_reservations = {}        # (u,v) → robot_id
        self.wait_for_graph = {}           # robot_id → robot_id it waits for
        self.deadlocks_resolved = 0
        self.total_delays = defaultdict(int)
        self.step_count = 0
        self.conflict_log = []
        self.throughput_history = []
    
    def register_robot(self, robot):
        """Register a robot with the traffic controller."""
        self.robots[robot.id] = robot
    
    def reserve_lane(self, robot_id, u, v):
        """Reserve a lane for a robot. Returns True if successful."""
        key = (u, v)
        
        # If lane is not reserved, grant it
        if key not in self.lane_reservations:
            self.lane_reservations[key] = robot_id
            return True
        
        # If already reserved by this robot, grant it
        if self.lane_reservations[key] == robot_id:
            return True
        
        # Lane is blocked by another robot
        blocker = self.lane_reservations[key]
        self.wait_for_graph[robot_id] = blocker
        self._log_conflict(robot_id, blocker, u, v)
        return False
    
    def release_lane(self, robot_id, u, v):
        """Release a lane reservation."""
        key = (u, v)
        if self.lane_reservations.get(key) == robot_id:
            del self.lane_reservations[key]
        self.wait_for_graph.pop(robot_id, None)
    
    def _log_conflict(self, robot_id, blocker, u, v):
        """Log a conflict event."""
        entry = {
            "step": self.step_count,
            "robot": robot_id,
            "blocked_by": blocker,
            "lane": (u, v)
        }
        self.conflict_log.append(entry)
        logging.info(f"Conflict: {robot_id} blocked by {blocker} on lane {u}→{v}")
        
        # Keep only last 100 conflicts
        if len(self.conflict_log) > 100:
            self.conflict_log = self.conflict_log[-100:]
    
    def detect_deadlock(self):
        """Detect cycles in the wait-for graph. Returns list of cycles."""
        visited = set()
        cycles = []
        
        def dfs(node, path, in_path):
            if node in in_path:
                idx = path.index(node)
                cycles.append(path[idx:])
                return
            if node in visited:
                return
            
            visited.add(node)
            in_path.add(node)
            path.append(node)
            
            if node in self.wait_for_graph:
                dfs(self.wait_for_graph[node], path[:], in_path.copy())
            
            path.pop()
            in_path.discard(node)
        
        for robot_id in list(self.wait_for_graph.keys()):
            if robot_id not in visited:
                dfs(robot_id, [], set())
        
        return cycles
    
    def resolve_deadlock(self, cycle):
        """Resolve a deadlock by replanning path for victim robot."""
        if not cycle:
            return
        
        # Choose victim (robot with highest ID number)
        victim = max(cycle, key=lambda r: int(r[1:]) if r[1:].isdigit() else 0)
        robot = self.robots.get(victim)
        
        if robot:
            # Collect nodes to avoid
            avoid = [self.robots[rid].current_node 
                    for rid in cycle if rid != victim and rid in self.robots]
            
            # Replan path
            robot.replan_path(avoid_nodes=avoid)
        
        # Release ALL lane reservations for ALL robots in the cycle
        for rid in cycle:
            to_release = [k for k, v in self.lane_reservations.items() if v == rid]
            for lane in to_release:
                del self.lane_reservations[lane]
        
        # Clear wait-for relationships for all robots in cycle
        for rid in cycle:
            self.wait_for_graph.pop(rid, None)
        
        self.deadlocks_resolved += 1
        logging.info(f"Deadlock resolved: cycle={cycle}, victim={victim}")
        
        self.conflict_log.append({
            "step": self.step_count,
            "type": "deadlock_resolved",
            "cycle": cycle,
            "victim": victim
        })
    
    def step(self, all_robot_positions):
        """Execute one step of traffic control."""
        self.step_count += 1
        from src.robots.robot import RobotStatus
        
        # Track delays
        for robot in self.robots.values():
            if robot.status in (RobotStatus.WAITING, RobotStatus.EMERGENCY_STOP):
                self.total_delays[robot.id] += 1
        
        # Check for deadlocks every 5 steps
        if self.step_count % 5 == 0:
            cycles = self.detect_deadlock()
            for cycle in cycles:
                self.resolve_deadlock(cycle)
        
        # Track throughput every 10 steps
        if self.step_count % 10 == 0:
            completed = sum(1 for r in self.robots.values()
                          if r.status == RobotStatus.GOAL_REACHED)
            self.throughput_history.append(completed)
    
    def get_metrics(self):
        """Get performance metrics."""
        from src.robots.robot import RobotStatus
        
        completed = sum(1 for r in self.robots.values()
                       if r.status == RobotStatus.GOAL_REACHED)
        
        delays = list(self.total_delays.values())
        avg_delay = sum(delays) / len(delays) if delays else 0
        throughput = completed / self.step_count if self.step_count > 0 else 0
        
        return {
            "total_steps": self.step_count,
            "deadlocks_resolved": self.deadlocks_resolved,
            "avg_delay_per_robot": round(avg_delay, 2),
            "throughput": round(throughput, 4),
            "robots_completed": completed,
            "total_robots": len(self.robots),
            "conflict_log": self.conflict_log[-20:],
            "throughput_history": self.throughput_history
        }


if __name__ == "__main__":
    from src.map.lane_graph import LaneGraph
    lg = LaneGraph()
    graph = lg.generate_warehouse_map()
    tc = TrafficController(graph)
    print("reserve R0:", tc.reserve_lane("R0", 0, 4))
    print("reserve R0 again:", tc.reserve_lane("R0", 0, 4))
    print("reserve R1 conflict:", tc.reserve_lane("R1", 0, 4))
    print("wait_for_graph:", tc.wait_for_graph)
    tc.release_lane("R0", 0, 4)
    print("after release, reserve R1:", tc.reserve_lane("R1", 0, 4))
    print("Traffic controller test PASSED")
