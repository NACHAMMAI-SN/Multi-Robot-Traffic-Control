# Changelog

## [Final] — April 19, 2026

### Added
- Battery management system with auto-charging and 
  emergency stops
- Checkpoint/resume — auto-save every 50 steps
- 3 unique scenarios: Night Shift, Peak Hours, 
  Emergency Evacuation
- Manual control mode — click robots to assign destinations
- Mode selection menu screen on startup
- Post-round screen — choose next mode/scenario after completion
- Scenario selection menu
- Emergency countdown timer with red flash effect
- Safety warnings when assigning paths through 
  CRITICAL/HUMAN_ZONE lanes
- Notification system — fade overlays for events
- Dynamic sidebar instructions (changes by manual mode state)
- Hover tooltips on robots and nodes
- Charging station visual markers on map
- Battery bars under each robot (color-coded)
- Support for 10 and 12 robots (scenario-dependent)
- `--scenario`, `--slow`, `--resume` CLI flags
- Correct X/8, X/10, X/12 completed display per scenario

### Core System (Initial Build)
- 20-node warehouse lane graph with full metadata
- A* pathfinding with euclidean heuristic
- Dynamic congestion-based routing weights
- Lane reservation for CRITICAL lanes
- Deadlock detection via wait-for graph + DFS
- Automatic deadlock resolution with victim replanning
- Lane heatmap with hotspot detection
- Pygame visualization at 60 FPS (1400×800)
- Emergency stops and safe following distance
- JSON results export and PNG heatmap export
- Staggered robot starts to prevent initial congestion
