import pygame
import sys
import json
import logging
import argparse
import yaml
import time
import networkx as nx
from datetime import datetime
from src.map.lane_graph import LaneGraph
from src.robots.robot import Robot, RobotStatus
from src.controller.traffic_controller import TrafficController
from src.heatmap.heatmap import LaneHeatmap
from src.battery.battery_manager import BatteryManager
from src.checkpoint.checkpoint_manager import CheckpointManager
from src.scenarios.scenario_manager import ScenarioManager
from src.visualization.simulator import (
    Simulator, WINDOW_W, WINDOW_H, MAP_W,
    BG, SUCCESS, WARNING, DANGER, ACCENT,
    TEXT_PRIMARY, TEXT_SECONDARY
)

logging.basicConfig(
    filename="simulation.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# Extended robot pairs for all scenarios (up to 12 robots)
ALL_ROBOT_PAIRS = [
    (0, 19), (1, 18), (2, 17), (3, 16),   # 8 standard
    (4, 15), (5, 14), (6, 13), (7, 12),
    (8, 11), (9, 10), (0, 14), (1, 13),   # 4 extra for peak hours
]

# Extended robot colors for up to 12 robots
ROBOT_COLORS = [
    (255, 100, 100), (100, 200, 255), (100, 255, 150), (255, 200, 80),
    (200, 100, 255), (255, 150, 50), (80, 255, 220), (255, 100, 200),
    (150, 255, 100), (255, 80, 150), (100, 255, 255), (200, 200, 100),
]

# Demo deadlock pairs - robots heading directly at each other
DEMO_DEADLOCK_PAIRS = [
    (4, 7), (7, 4),  # Meet on critical lane 5-6
    (8, 11), (11, 8),  # Meet on critical intersection lanes
    (2, 6), (6, 2),
    (3, 7), (7, 3),
]


def load_config(path="config.yaml"):
    """Load configuration from YAML file."""
    try:
        with open(path) as f:
            return yaml.safe_load(f)
    except:
        return {"simulation": {"num_robots": 8, "max_steps": 1000}}


def run_simulation(headless=False, max_steps=1000, num_robots=8, mode="auto", slow=False, 
                   existing_screen=None, scenario="night_shift", resume=False, demo_deadlock=False):
    """Run the multi-robot traffic control simulation."""
    config = load_config()
    max_steps = max_steps or config.get("simulation", {}).get("max_steps", 1000)

    # Generate warehouse map
    lg_builder = LaneGraph()
    lane_graph = lg_builder.generate_warehouse_map()
    logging.info(f"Map: {len(lane_graph.get_all_nodes())} nodes, {len(lane_graph.get_all_edges())} edges")

    # Initialize systems
    heatmap = LaneHeatmap(lane_graph)
    tc = TrafficController(lane_graph)

    # Create robots with staggered starts to reduce initial congestion
    pairs = ALL_ROBOT_PAIRS[:num_robots]
    robots = []
    for i, (start, goal) in enumerate(pairs):
        color = ROBOT_COLORS[i % len(ROBOT_COLORS)]
        r = Robot(f"R{i}", start, goal, lane_graph, color)
        r.compute_path()
        # Stagger start times - each robot waits i*5 steps before starting
        r.start_delay = i * 5
        tc.register_robot(r)
        robots.append(r)
        logging.info(f"R{i}: {start}→{goal} path={r.path} start_delay={r.start_delay}")

    # Override for demo deadlock mode
    if demo_deadlock:
        # Use ONLY 2 robots for guaranteed collision
        num_robots = 2
        pairs = DEMO_DEADLOCK_PAIRS[:2]  # (0→19) and (19→0)
        robots = []
        for i, (start, goal) in enumerate(pairs):
            color = ROBOT_COLORS[i % len(ROBOT_COLORS)]
            r = Robot(f"R{i}", start, goal, lane_graph, color)
            success = r.compute_path()
            if not success or not r.path:
                print(f"WARNING: Could not compute path for R{i} from {start} to {goal}!")
                print(f"  Graph has edge {start}->{goal}? {lane_graph.graph.has_edge(start, goal)}")
                print(f"  Graph has edge {goal}->{start}? {lane_graph.graph.has_edge(goal, start)}")
            tc.register_robot(r)
            robots.append(r)
            logging.info(f"DEMO DEADLOCK - R{i}: {start}->{goal} path={r.path}")
        
        # Remove staggered starts - all start together
        for r in robots:
            r.start_delay = 0
            r.status = RobotStatus.IDLE  # Make sure they're active
        
        # Disable auto-replanning to let deadlock form
        for r in robots:
            r.stuck_replan_threshold = 9999
        
        print(f"R0: {robots[0].current_node}->{robots[0].goal_node}, path: {robots[0].path}")
        print(f"R1: {robots[1].current_node}->{robots[1].goal_node}, path: {robots[1].path}")

    # Apply scenario modifications
    sm = ScenarioManager()
    sm.apply(scenario, lane_graph, robots)
    
    # Create battery manager
    battery_manager = BatteryManager(robots)
    
    # Create checkpoint manager
    ckpt = CheckpointManager(save_every=50)
    
    # Resume from checkpoint if requested
    start_step = 1
    if resume and ckpt.exists():
        data = ckpt.load()
        if data:
            # Restore robot states
            robot_data = {r["id"]: r for r in data["robots"]}
            for robot in robots:
                if robot.id in robot_data:
                    rd = robot_data[robot.id]
                    robot.current_node = rd["current_node"]
                    robot.goal_node = rd["goal_node"]
                    robot.path = rd.get("path", [])
                    robot.path_index = rd.get("path_index", 0)
                    robot.replan_count = rd.get("replan_count", 0)
                    robot.steps_waiting = rd.get("steps_waiting", 0)
                    # Restore battery
                    battery_manager.batteries[robot.id] = rd.get("battery", 100.0)
            # Restore heatmap
            for key_str, count in data.get("heatmap_usage", {}).items():
                parts = key_str.split(",")
                if len(parts) == 2:
                    try:
                        u, v = int(parts[0]), int(parts[1])
                        heatmap.usage_count[(u, v)] = count
                    except: pass
            # Restore TC stats
            tc.deadlocks_resolved = data.get("deadlocks_resolved", 0)
            start_step = data["step"] + 1
            print(f"Resumed from step {data['step']}")

    # Initialize simulator if not headless
    sim = None
    if not headless:
        sim = Simulator(lane_graph, robots, tc, heatmap, existing_screen=existing_screen,
                       battery_manager=battery_manager, scenario=scenario, max_steps=max_steps, mode=mode)
        sim.instruction_timer = 300
        if resume and start_step > 1:
            sim.add_notification(f"Resumed from checkpoint (Step {start_step - 1})! 💾", ACCENT)

    prev_completed = 0
    prev_deadlocks = 0
    step = 0

    # AUTO MODE - existing functionality
    if mode == "auto":
        # Add startup notification
        if sim:
            sim.add_notification("Simulation Started! 8 robots navigating...", SUCCESS)
        
        for step in range(start_step, max_steps + 1):
            # Handle visualization
            if sim is not None:
                should_advance = sim.tick()
                if not sim.running:
                    break
                if not should_advance:
                    continue
                sim.update_step(step)

            # Get all robot positions
            all_positions = {r.id: r.current_node for r in robots}

            # Move all robots
            for robot in robots:
                robot.move_step(robots, tc, heatmap, step)
            
            # Update batteries and handle low battery
            for robot in robots:
                bat = battery_manager.update(robot, step)
                if battery_manager.is_dead(robot.id):
                    robot.emergency_stop()
                    if sim:
                        sim.add_notification(f"{robot.id} battery DEAD! ☠️", DANGER)
                elif battery_manager.needs_charging(robot.id):
                    if not battery_manager.is_at_charger(robot):
                        nearest = battery_manager.get_nearest_charger(robot)
                        if robot.goal_node != nearest:
                            robot.goal_node = nearest
                            robot.replan_path()
                            if sim:
                                sim.add_notification(
                                    f"{robot.id} low battery! Going to charge ⚡",
                                    WARNING)

            # Update occupancy
            occupancy = {}
            for robot in robots:
                lane = robot.get_current_lane()
                if lane:
                    occupancy[lane] = occupancy.get(lane, 0) + 1
            for lane, count in occupancy.items():
                heatmap.set_occupancy(lane[0], lane[1], count)

            # Traffic control step (force deadlock check every step in demo mode)
            tc.step(all_positions, force_deadlock_check=demo_deadlock)
            heatmap.snapshot(step)
            
            # Checkpoint save
            if ckpt.should_save(step):
                ckpt.save(step, robots, tc, heatmap, battery_manager, mode, scenario)
                if sim:
                    sim.add_notification(f"Checkpoint saved ✓ (Step {step})", 
                                       TEXT_SECONDARY, duration=90)
            
            # Slow motion for recording
            if not headless and mode == "auto":
                if slow:
                    time.sleep(0.08)   # slower motion for --slow flag
                else:
                    time.sleep(0.03)   # default auto speed (more watchable)

            # Visual effects
            if sim:
                cur = sum(1 for r in robots if r.status == RobotStatus.GOAL_REACHED)
                if cur > prev_completed:
                    for r in robots:
                        if r.status == RobotStatus.GOAL_REACHED and r.goal_reached_step == step:
                            sim.add_effect("goal", r.current_node, 70)
                            sim.add_notification(f"{r.id} reached goal! 🎯", SUCCESS)
                prev_completed = cur
                
                if tc.deadlocks_resolved > prev_deadlocks:
                    for r in robots:
                        if r.status in (RobotStatus.WAITING, RobotStatus.EMERGENCY_STOP):
                            sim.add_effect("deadlock", r.current_node, 40)
                    print(f"DEADLOCK DETECTED AND RESOLVED! Total: {tc.deadlocks_resolved}")
                    sim.add_notification(
                        f"DEADLOCK RESOLVED! ({tc.deadlocks_resolved} total)",
                        DANGER, duration=300)
                    prev_deadlocks = tc.deadlocks_resolved
                
                for r in robots:
                    if r.emergency_flash_timer == 29:
                        sim.add_effect("emergency", r.current_node, 50)

            # Periodic logging
            if step % 50 == 0:
                m = tc.get_metrics()
                logging.info(f"Step {step}: done={m['robots_completed']} deadlocks={m['deadlocks_resolved']}")

            # Check completion
            if all(r.status == RobotStatus.GOAL_REACHED for r in robots):
                logging.info(f"All done at step {step}")
                if sim:
                    time.sleep(1.5)
                break
    
    # MANUAL MODE - interactive functionality
    else:  # mode == "manual"
        # Initial notification
        if sim:
            sim.add_notification("Assign destinations to all 8 robots! Click each robot then click a node", ACCENT, duration=300)
        
        step = start_step
        prev_assigned_count = 0
        prev_deadlocks = 0
        
        # Track manual mode completions (robots reset to IDLE after reaching goal)
        manual_completions = {r.id: 0 for r in robots}
        
        # INFINITE LOOP - only exits when user presses Q
        try:
            while sim.running:
                # Handle events manually to catch mouse clicks
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        sim.running = False
                        break
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_q:
                            sim.running = False
                            break
                        if event.key == pygame.K_SPACE:
                            sim.paused = not sim.paused
                        if event.key == pygame.K_h:
                            sim.show_heatmap = not sim.show_heatmap
                            if sim.show_heatmap:
                                sim.add_notification("Heatmap ON - showing congestion", ACCENT)
                            else:
                                sim.add_notification("Heatmap OFF - showing lane types", ACCENT)
                        if event.key == pygame.K_ESCAPE:
                            sim.selected_robot = None
                        if event.key == pygame.K_UP:
                            sim.cam[1] += 20
                        if event.key == pygame.K_DOWN:
                            sim.cam[1] -= 20
                        if event.key == pygame.K_LEFT:
                            sim.cam[0] += 20
                        if event.key == pygame.K_RIGHT:
                            sim.cam[0] -= 20
                        for i in range(8):
                            key_attr = f"K_{i+1}"
                            if hasattr(pygame, key_attr):
                                if event.key == getattr(pygame, key_attr) and i < len(robots):
                                    sim.selected_robot = robots[i]
                                    sim.add_notification(
                                        f"{robots[i].id} selected! Click a node to assign goal",
                                        WARNING)
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        # Check deadlock button first (in sidebar)
                        button_clicked = False
                        if hasattr(sim, 'deadlock_btn') and sim.deadlock_btn is not None:
                            if sim.deadlock_btn.collidepoint(event.pos):
                                sim.force_deadlock_requested = True
                                button_clicked = True
                        
                        # Then check map clicks (only if button wasn't clicked)
                        if not button_clicked and event.pos[0] < MAP_W:
                            action, data = sim.handle_manual_click(event.pos)
                            if action == "select_robot":
                                sim.selected_robot = data
                                sim.add_notification(
                                    f"{data.id} selected! Click a node to assign goal",
                                    WARNING)
                            elif action == "assign_goal":
                                robot, node = data
                                
                                # SAFETY WARNINGS - Check path before assignment
                                try:
                                    temp_path = nx.astar_path(
                                        lane_graph.graph, 
                                        robot.current_node,
                                        node,
                                        weight=lambda u,v,d: lane_graph.get_routing_weight(u,v)
                                    )
                                    
                                    warnings = []
                                    for i in range(len(temp_path)-1):
                                        u, v = temp_path[i], temp_path[i+1]
                                        meta = lane_graph.get_lane_metadata(u, v)
                                        if meta:
                                            lane_type = meta.get('lane_type')
                                            safety = meta.get('safety_level')
                                            if safety and safety.name == 'CRITICAL':
                                                warnings.append(f"⚠️ Path crosses CRITICAL lane {u}→{v}!")
                                            if lane_type and lane_type.name == 'HUMAN_ZONE':
                                                warnings.append(f"🚶 Path enters HUMAN ZONE at lane {u}→{v}!")
                                            if lane_type and lane_type.name == 'NARROW':
                                                warnings.append(f"⚠️ Path uses NARROW lane {u}→{v}")
                                    
                                    # Check destination area congestion
                                    for neighbor in lane_graph.graph.neighbors(node):
                                        meta = lane_graph.get_lane_metadata(node, neighbor)
                                        if meta and meta.get('congestion_score', 0) > 0.5:
                                            warnings.append(f"⚠️ Node {node} area is congested!")
                                            break
                                    
                                    # Show warnings or success
                                    if warnings:
                                        for w in warnings[:2]:  # Max 2 warnings
                                            sim.add_notification(w, WARNING, duration=240)
                                    else:
                                        sim.add_notification(f"{robot.id} → Node {node}: Safe path! ✓", SUCCESS)
                                except:
                                    pass
                                
                                # Assign goal
                                old_goal = robot.goal_node
                                robot.goal_node = node
                                robot.replan_path()
                                robot.status = RobotStatus.IDLE
                                sim.target_nodes[robot.id] = node
                                sim.assigned_robots.add(robot.id)
                                sim.add_notification(
                                    f"{robot.id} assigned to Node {node}! Navigating...",
                                    SUCCESS)
                                
                                # Check if all 8 assigned for first time
                                if len(sim.assigned_robots) == 8 and prev_assigned_count < 8:
                                    sim.add_notification("All robots assigned! Great coordination! 🎉", SUCCESS, duration=240)
                                prev_assigned_count = len(sim.assigned_robots)
                
                if not sim.running:
                    break
                if sim.paused:
                    sim.render()
                    sim.clock.tick(60)
                    continue
                
                # ---- Force Deadlock Handler ----
                if getattr(sim, 'force_deadlock_requested', False):
                    sim.force_deadlock_requested = False
                    try:
                        moving = [
                            r for r in robots
                            if r.status in (
                                RobotStatus.MOVING,
                                RobotStatus.WAITING,
                                RobotStatus.IDLE)
                            and r.goal_node is not None
                            and r.goal_node != r.current_node
                            and r.path
                            and len(r.path) > 1
                        ]

                        if len(moving) < 2:
                            sim.add_notification(
                                "Assign 2 robots with destinations first!",
                                color=(255, 150, 0),
                                duration=200)
                        else:
                            r0 = moving[0]
                            r1 = moving[1]

                            r0.stuck_replan_threshold = 50
                            r1.stuck_replan_threshold = 50

                            sim._demo_r0_id = r0.id
                            sim._demo_r1_id = r1.id
                            sim._demo_r0_goal = r0.goal_node
                            sim._demo_r1_goal = r1.goal_node

                            r0.goal_node = r1.current_node
                            r1.goal_node = r0.current_node

                            r0.replan_path()
                            r1.replan_path()

                            r0.status = RobotStatus.MOVING
                            r1.status = RobotStatus.MOVING
                            r0.steps_waiting = 0
                            r1.steps_waiting = 0
                            r0.emergency_flash_timer = 0
                            r1.emergency_flash_timer = 0

                            sim.target_nodes[r0.id] = r0.goal_node
                            sim.target_nodes[r1.id] = r1.goal_node

                            sim.add_notification(
                                f"Demo: {r0.id} vs {r1.id}!",
                                color=(255, 120, 0),
                                duration=300)
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                # ---- End Force Deadlock Handler ----

                # Move ALL robots that have assigned targets
                all_positions = {r.id: r.current_node for r in robots}
                for robot in robots:
                    if robot.id in sim.target_nodes:
                        # Start IDLE robots that have assignments
                        if robot.status == RobotStatus.IDLE:
                            robot.status = RobotStatus.MOVING
                        # Move robots that aren't at goal
                        if robot.status != RobotStatus.GOAL_REACHED:
                            robot.move_step(robots, tc, heatmap, step)
                
                # Update batteries for all robots
                for robot in robots:
                    bat = battery_manager.update(robot, step)
                    if battery_manager.is_dead(robot.id):
                        robot.emergency_stop()
                        sim.add_notification(f"{robot.id} battery DEAD! ☠️", DANGER)
                
                # Handle goal completion (after battery update)
                for robot in robots:
                    if robot.status == RobotStatus.GOAL_REACHED and robot.id in sim.target_nodes:

                        # Skip demo robots — let deadlock handler restore them instead
                        if robot.id in (
                            getattr(sim, '_demo_r0_id', None),
                            getattr(sim, '_demo_r1_id', None)):
                            continue

                        goal_node = sim.target_nodes[robot.id]
                        sim.add_notification(f"{robot.id} reached Node {goal_node}! Assign new destination 🎯", SUCCESS, duration=240)
                        sim.add_effect("goal", robot.current_node, 70)
                        # Track completion for metrics
                        manual_completions[robot.id] += 1
                        # Reset robot for new assignment
                        del sim.target_nodes[robot.id]
                        sim.completed_trips.add(robot.id)
                        robot.status = RobotStatus.IDLE
                        robot.goal_reached_step = step

                # Update occupancy
                occupancy = {}
                for robot in robots:
                    lane = robot.get_current_lane()
                    if lane:
                        occupancy[lane] = occupancy.get(lane, 0) + 1
                for lane, count in occupancy.items():
                    heatmap.set_occupancy(lane[0], lane[1], count)

                tc.step(all_positions)
                heatmap.snapshot(step)
                
                # ---- Deadlock Resolved Handler ----
                if tc.deadlocks_resolved > prev_deadlocks:
                    prev_deadlocks = tc.deadlocks_resolved
                    try:
                        if hasattr(sim, '_demo_r0_id'):
                            for r in robots:
                                if r.id == sim._demo_r0_id:
                                    r.goal_node = sim._demo_r0_goal
                                    r.replan_path()
                                    r.status = RobotStatus.MOVING
                                    r.stuck_replan_threshold = 15
                                    sim.target_nodes[r.id] = sim._demo_r0_goal
                                elif r.id == sim._demo_r1_id:
                                    r.goal_node = sim._demo_r1_goal
                                    r.replan_path()
                                    r.status = RobotStatus.MOVING
                                    r.stuck_replan_threshold = 15
                                    sim.target_nodes[r.id] = sim._demo_r1_goal

                            del sim._demo_r0_id
                            del sim._demo_r1_id
                            del sim._demo_r0_goal
                            del sim._demo_r1_goal

                            sim.add_notification(
                                "Deadlock Resolved! Robots back to original goals!",
                                color=(50, 220, 100),
                                duration=300)
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                # ---- End Deadlock Resolved Handler ----
                
                # Checkpoint save
                if ckpt.should_save(step):
                    ckpt.save(step, robots, tc, heatmap, battery_manager, mode, scenario)
                    sim.add_notification(f"Checkpoint saved ✓ (Step {step})", 
                                       TEXT_SECONDARY, duration=90)
                
                # Slow motion for recording
                if slow:
                    time.sleep(0.1)
                
                step += 1

                sim.update_step(step)
                sim.render()
                sim.clock.tick(60)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Manual loop error: {e}")
            return "menu"  # go back to menu, not quit
    
    # ============================================================
    # METRICS CALCULATION AND PRINTING - RUNS FOR BOTH MODES
    # This block ALWAYS executes regardless of how loops ended
    # ============================================================
    
    # Calculate metrics
    metrics = tc.get_metrics()
    metrics["total_steps"] = step  # Add step count for post-round screen
    
    # Ensure metrics have correct robot counts
    total_robots = len(robots)
    
    # Override metrics for manual mode (robots get reset to IDLE after reaching goals)
    if mode == "manual":
        total_completed = sum(1 for v in manual_completions.values() if v > 0)
        total_completed = min(total_completed, total_robots)
        metrics["robots_completed"] = total_completed
        metrics["throughput"] = round(total_completed / step if step > 0 else 0, 4)
        metrics["manual_completions"] = manual_completions
        metrics["total_robots"] = total_robots
    else:
        # Auto mode - ensure completed doesn't exceed total
        metrics["robots_completed"] = min(metrics["robots_completed"], total_robots)
        metrics["total_robots"] = total_robots
    
    # Save results to JSON
    results = {
        "timestamp": datetime.now().isoformat(),
        "simulation_steps": step,
        "scenario": scenario,
        "mode": mode,
        "total_robots": len(robots),
        "robots_completed": metrics["robots_completed"],
        "completion_rate": f"{metrics['robots_completed']}/{len(robots)}",
        "metrics": metrics,
        "heatmap_stats": heatmap.export_stats(),
        "trajectories": {r.id: r.get_trajectory() for r in robots},
        "robot_summary": [
            {
                "id": r.id,
                "start": pairs[i][0],
                "goal": pairs[i][1],
                "status": r.status.name,
                "replan_count": r.replan_count,
                "steps_waiting": r.steps_waiting,
                "goal_reached_step": r.goal_reached_step
            }
            for i, r in enumerate(robots)
        ]
    }
    
    # Add manual completions to results if in manual mode
    if mode == "manual":
        results["manual_completions"] = manual_completions
    
    # Add battery stats (already has scenario in results dict above)
    results["battery_stats"] = battery_manager.export_stats()
    
    # Generate scenario-specific heatmap filename
    heatmap_filename = f"heatmap_{scenario}.png"
    results["heatmap_file"] = heatmap_filename
    
    with open("results_summary.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    lane_graph.export_heatmap_image(heatmap_filename)
    
    # ALWAYS print to terminal (both AUTO and MANUAL)
    total_robots = len(robots)
    completed = min(metrics['robots_completed'], total_robots)
    
    print("\n" + "=" * 50)
    print("SIMULATION COMPLETE")
    print(f"Mode:       {'AUTO' if mode=='auto' else 'MANUAL'}")
    print(f"Steps:      {step}")
    print(f"Completed:  {completed}/{total_robots}")
    print(f"Deadlocks:  {metrics['deadlocks_resolved']}")
    print(f"Avg Delay:  {metrics['avg_delay_per_robot']:.2f}")
    print(f"Throughput: {metrics['throughput']:.4f}")
    print("=" * 50)
    
    # Show post-round screen (GUI mode only)
    if sim is not None and not headless:
        next_choice = sim.show_post_round_screen(mode, metrics)
        return next_choice
    return "quit"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--steps", type=int, default=1000)
    parser.add_argument("--robots", type=int, default=8)
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--slow", action="store_true")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument(
        "--scenario",
        choices=["night_shift", "peak_hours", "emergency"],
        default="night_shift",
        help="Scenario: night_shift, peak_hours, emergency"
    )
    parser.add_argument(
        "--demo-deadlock",
        action="store_true",
        help="Force deadlock scenario for demonstration"
    )
    args = parser.parse_args()

    # Block 1: Test mode
    if args.test:
        print("Running 50-step test...")
        run_simulation(
            headless=True,
            max_steps=50,
            num_robots=8,
            scenario="test",
            resume=args.resume,
            demo_deadlock=args.demo_deadlock
        )
        print("TEST PASSED")
        sys.exit(0)
    
    # Block 2: Headless mode
    if args.headless:
        # Determine max_steps - user flag always wins
        sm = ScenarioManager()
        scenario_default = sm.SCENARIOS.get(args.scenario, {}).get("max_steps", 1000)
        
        # If user passed --steps explicitly (not default 1000), use their value
        # Otherwise use scenario default
        if args.steps != 1000:
            final_steps = args.steps
        else:
            final_steps = scenario_default
        
        num_robots = sm.SCENARIOS.get(args.scenario, {}).get("robots", 8)
        
        run_simulation(
            headless=True,
            max_steps=final_steps,
            num_robots=num_robots,
            scenario=args.scenario,
            resume=args.resume,
            demo_deadlock=args.demo_deadlock
        )
        sys.exit(0)

    # Block 3: GUI mode (everything else including --slow, --demo-deadlock, --resume, or no flags)
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    pygame.display.set_caption("Multi-Robot Traffic Control System")
    f_large = pygame.font.SysFont("arial", 26, bold=True)
    f_med   = pygame.font.SysFont("arial", 17, bold=True)
    f_small = pygame.font.SysFont("arial", 13)
    lc = pygame.time.Clock()

    def show_main_menu():
        btn_auto   = pygame.Rect(200, 320, 400, 180)
        btn_manual = pygame.Rect(800, 320, 400, 180)
        while True:
            mp = pygame.mouse.get_pos()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "quit"
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_1: return "auto"
                    if event.key == pygame.K_2: return "manual"
                    if event.key == pygame.K_q:
                        return "quit"
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if btn_auto.collidepoint(mp):   return "auto"
                    if btn_manual.collidepoint(mp): return "manual"
            
            screen.fill((15, 15, 35))
            
            # Title
            t = f_large.render(
                "Multi-Robot Traffic Control System", True, (120,200,255))
            screen.blit(t, (WINDOW_W//2 - t.get_width()//2, 160))
            
            # Buttons
            for rect, label, sub, color, key in [
                (btn_auto,   "AUTO MODE",
                 "Watch 8 robots navigate automatically",
                 (80,220,120),  "1"),
                (btn_manual, "MANUAL MODE",
                 "You control robot destinations",
                 (100,180,255), "2"),
            ]:
                hover = rect.collidepoint(mp)
                dark  = tuple(max(0, c//4) for c in color)
                edge  = tuple(min(255,c+40) for c in color) if hover else color
                pygame.draw.rect(screen, dark, rect, border_radius=14)
                pygame.draw.rect(screen, edge, rect, border_radius=14, width=3)
                l = f_large.render(label, True, (255,255,255))
                s = f_small.render(sub,   True, (200,200,220))
                k = f_med.render(f"[{key}]", True, edge)
                screen.blit(l,(rect.centerx-l.get_width()//2, rect.y+30))
                screen.blit(s,(rect.centerx-s.get_width()//2, rect.y+80))
                screen.blit(k,(rect.centerx-k.get_width()//2, rect.y+125))
            
            # Hints
            h = f_small.render(
                "[1] Auto Mode       [2] Manual Mode       [Q] Quit",
                True, (150,150,180))
            screen.blit(h, (WINDOW_W//2 - h.get_width()//2, WINDOW_H-50))
            
            pygame.display.flip()
            lc.tick(60)
    
    def show_scenario_menu():
        """Show scenario selection menu."""
        scenarios = [
            ("night_shift", "🌙 Night Shift",
             "8 robots | Maintenance lanes closed | Reduced speeds",
             (80, 80, 180), "1"),
            ("peak_hours", "⚡ Peak Hours",
             "12 robots | Pre-congested | Intersection bottlenecks",
             (200, 140, 40), "2"),
            ("emergency", "🚨 Emergency Evacuation",
             "10 robots | 300 step countdown | Race to safe zones",
             (200, 50, 50), "3"),
        ]
        
        btns = [pygame.Rect(100, 250 + i*160, 1200, 130) for i in range(3)]
        
        while True:
            mp = pygame.mouse.get_pos()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "quit"
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_1: return "night_shift"
                    if event.key == pygame.K_2: return "peak_hours"
                    if event.key == pygame.K_3: return "emergency"
                    if event.key == pygame.K_q: return "quit"
                    if event.key == pygame.K_ESCAPE: return "quit"
                if event.type == pygame.MOUSEBUTTONDOWN:
                    for i, btn in enumerate(btns):
                        if btn.collidepoint(mp):
                            return scenarios[i][0]
            
            screen.fill((15, 15, 35))
            
            title = f_large.render("Choose Scenario", True, (120, 200, 255))
            screen.blit(title, (700 - title.get_width()//2, 120))
            back = f_small.render("[ESC] Back to mode selection", True, (100, 100, 150))
            screen.blit(back, (700 - back.get_width()//2, 170))
            
            for i, (key, name, desc, color, num) in enumerate(scenarios):
                btn = btns[i]
                hover = btn.collidepoint(mp)
                dark = tuple(max(0, c//3) for c in color)
                edge = tuple(min(255,c+50) for c in color) if hover else color
                pygame.draw.rect(screen, dark, btn, border_radius=12)
                pygame.draw.rect(screen, edge, btn, border_radius=12, width=3)
                n = f_large.render(name, True, (255,255,255))
                d = f_small.render(desc, True, (200,200,220))
                k = f_med.render(f"[{num}]", True, edge)
                screen.blit(n, (btn.x+20, btn.y+18))
                screen.blit(d, (btn.x+20, btn.y+58))
                screen.blit(k, (btn.right-60, btn.y+42))
            
            hints = f_small.render(
                "[1] Night Shift   [2] Peak Hours   [3] Emergency   [Q] Quit",
                True, (150, 150, 180))
            screen.blit(hints, (700 - hints.get_width()//2, 750))
            
            pygame.display.flip()
            lc.tick(60)

    # Game loop - mode and scenario selection with KeyboardInterrupt protection
    try:
        current_mode = show_main_menu()
        if current_mode == "quit":
            pygame.quit()
            sys.exit(0)
        
        current_scenario = show_scenario_menu()
        if current_scenario == "quit":
            pygame.quit()
            sys.exit(0)
        
        # Get scenario configuration
        sm = ScenarioManager()
        num_robots = sm.SCENARIOS[current_scenario]["robots"]
        max_steps = sm.SCENARIOS[current_scenario]["max_steps"]

        while True:
            next_mode = run_simulation(
                headless=False,
                max_steps=max_steps,
                num_robots=num_robots,
                mode=current_mode,
                slow=args.slow,
                existing_screen=screen,
                scenario=current_scenario,
                resume=args.resume,
                demo_deadlock=args.demo_deadlock
            )
            if next_mode is None or next_mode == "quit":
                break
            
            # After post round screen, ask scenario again
            current_mode = next_mode
            if current_mode not in (None, "quit"):
                current_scenario = show_scenario_menu()
                if current_scenario == "quit":
                    break
                num_robots = sm.SCENARIOS[current_scenario]["robots"]
                max_steps = sm.SCENARIOS[current_scenario]["max_steps"]
                args.resume = False  # Don't resume again after first round
    except KeyboardInterrupt:
        pass
    finally:
        pygame.quit()
        sys.exit(0)
