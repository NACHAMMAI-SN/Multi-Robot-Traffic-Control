# Features

**Last Updated:** April 19, 2026

## Core Features (Problem Statement Requirements)

### Lane Graph with Metadata
- 20-node warehouse map, 50 directed lanes
- Per-lane: max_speed, safety_level (LOW/MEDIUM/HIGH/CRITICAL),
  lane_type (NORMAL/NARROW/INTERSECTION/HUMAN_ZONE),
  congestion_score, historical_usage_count

### A* Pathfinding
- Euclidean heuristic
- Dynamic routing weights penalize congested lanes
- Automatic replanning on block or deadlock

### Lane-Based Speed Control
- NARROW lanes: 60% of base speed
- HUMAN_ZONE lanes: 40% of base speed
- INTERSECTION lanes: 70% of base speed
- Congestion >0.3: 75%, >0.5: 50%, >0.7: 30%

### Collision Avoidance
- 1-node minimum gap enforced
- Emergency stop if next node occupied by active robot
- GOAL_REACHED robots ignored (they won't move)

### Lane Reservation System
- CRITICAL lanes require reservation before entry
- Robot waits if reservation denied
- Force replan after 15 steps waiting

### Deadlock Detection & Resolution
- Wait-for graph built every 5 steps
- DFS cycle detection
- Victim (highest ID) replanned, all cycle reservations released
- Zero unresolved deadlocks in testing

### Lane Heatmap
- Real-time occupancy tracking per lane
- Historical usage count
- Congestion score = f(occupancy + history)
- Color: green (<0.3) → yellow (0.3-0.7) → red (>0.7)
- Top 5 hotspots displayed in sidebar

## Bonus Features

### Battery Management
- Per-robot battery starting at 100%
- Auto-reroute to charger (nodes 3,7,11,15) when <10%
- Emergency stop when dead (<2%)
- Visual battery bar under each robot (color-coded)
- Lane type affects drain rate

### Checkpoint & Resume
- Auto-saves every 50 steps to checkpoint.json
- Saves: robot positions, paths, battery, heatmap, tc state
- Resume with `--resume` flag
- Notification shown on save/resume

### 3 Unique Scenarios
| Scenario | Robots | Steps | Special |
|---|---|---|---|
| 🌙 Night Shift | 8 | 800 | 4 lanes closed, 30% slower |
| ⚡ Peak Hours | 12 | 1000 | Pre-congested, bottleneck intersections |
| 🚨 Emergency | 10 | 300 | Countdown timer, race to safe zones |

### Dual Control Modes
- **Auto Mode**: Robots navigate fully automatically
- **Manual Mode**: Click robots → click nodes to assign destinations
  - Up to 8 simultaneous active assignments
  - Safety warnings shown for CRITICAL/HUMAN_ZONE paths
  - Dynamic sidebar instructions change based on state

### Pygame Visualization (1400×800, 60 FPS)
- Color-coded lanes by type and safety level
- Robot avatars with status rings and glow effects
- Path preview dots (next 6 nodes)
- Live sidebar: metrics, robot table, congestion hotspots, throughput graph
- Notification system (top-center fade overlays)
- Visual effects: goal rings, emergency banners, deadlock alerts

### Interactive Controls
| Key | Action |
|---|---|
| H | Toggle heatmap overlay |
| SPACE | Pause / Resume |
| ↑↓←→ | Pan camera |
| 1-8 | Select robot (manual mode) |
| ESC | Deselect robot |
| Q | Quit |

## Performance Results

| Scenario | Robots | Steps to Complete | Deadlocks |
|---|---|---|---|
| Night Shift | 8 | ~383 | 0 |
| Peak Hours | 12 | ~450 | varies |
| Emergency | 10 | ~85 | 0 |
