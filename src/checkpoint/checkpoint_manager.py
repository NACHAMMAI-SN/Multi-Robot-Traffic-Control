"""Checkpoint and resume system for simulations."""
import json
import os
from datetime import datetime

CHECKPOINT_FILE = "checkpoint.json"


class CheckpointManager:
    """Manages saving and loading simulation checkpoints."""
    
    def __init__(self, save_every=50):
        self.save_every = save_every
        self.last_saved = 0
    
    def should_save(self, step) -> bool:
        """Check if checkpoint should be saved at this step."""
        return (step % self.save_every == 0 
                and step != self.last_saved 
                and step > 0)
    
    def save(self, step, robots, tc, heatmap, battery_manager, mode, scenario) -> bool:
        """Save checkpoint of current simulation state."""
        try:
            state = {
                "timestamp": datetime.now().isoformat(),
                "step": step,
                "mode": mode,
                "scenario": scenario,
                "robots": [
                    {
                        "id": r.id,
                        "current_node": r.current_node,
                        "goal_node": r.goal_node,
                        "status": r.status.name,
                        "path": r.path,
                        "path_index": r.path_index,
                        "replan_count": r.replan_count,
                        "steps_waiting": r.steps_waiting,
                        "goal_reached_step": r.goal_reached_step,
                        "battery": battery_manager.batteries.get(r.id, 100.0)
                    }
                    for r in robots
                ],
                "lane_reservations": {
                    f"{k[0]},{k[1]}": v
                    for k, v in tc.lane_reservations.items()
                },
                "deadlocks_resolved": tc.deadlocks_resolved,
                "heatmap_usage": {
                    f"{k[0]},{k[1]}": v
                    for k, v in heatmap.usage_count.items()
                }
            }
            with open(CHECKPOINT_FILE, "w") as f:
                json.dump(state, f, indent=2, default=str)
            self.last_saved = step
            return True
        except Exception as e:
            print(f"Checkpoint save failed: {e}")
            return False
    
    def exists(self) -> bool:
        """Check if checkpoint file exists."""
        return os.path.exists(CHECKPOINT_FILE)
    
    def load(self) -> dict:
        """Load checkpoint data."""
        if not self.exists():
            return None
        try:
            with open(CHECKPOINT_FILE) as f:
                return json.load(f)
        except:
            return None
    
    def delete(self):
        """Delete checkpoint file."""
        if os.path.exists(CHECKPOINT_FILE):
            os.remove(CHECKPOINT_FILE)
    
    def get_info(self) -> str:
        """Get human-readable checkpoint info."""
        data = self.load()
        if not data:
            return None
        return (f"Step {data['step']} | "
                f"{data['mode'].upper()} | "
                f"{data['scenario']} | "
                f"{data['timestamp'][:16]}")
