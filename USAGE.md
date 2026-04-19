# Usage Guide

**Last Updated:** April 19, 2026

## Installation

```bash
cd multi_robot_traffic_control
python -m pip install -r requirements.txt
```

**Requirements:** Python 3.10+, see requirements.txt

## Running the Simulation

### GUI Mode (recommended)
```bash
python main.py
```
1. Menu appears → choose **Auto** or **Manual** mode
2. Scenario menu → choose **Night Shift**, **Peak Hours**, or **Emergency**
3. Simulation runs with full pygame visualization
4. After completion → post-round screen asks what to do next

### Headless Mode
```bash
# Default scenario (night_shift), default steps
python main.py --headless

# Specific scenario
python main.py --headless --scenario peak_hours

# Specific steps
python main.py --headless --scenario emergency --steps 150

# Resume from checkpoint
python main.py --headless --resume
```

### Slow Motion (for recording)
```bash
python main.py --slow
```

### Quick Test (50 steps, no GUI)
```bash
python main.py --test
# Must print: TEST PASSED
```

## All Command-Line Flags

| Flag | Description | Default |
|---|---|---|
| `--headless` | Run without GUI | false |
| `--steps N` | Max simulation steps | scenario default |
| `--robots N` | Number of robots | scenario default |
| `--scenario X` | night_shift / peak_hours / emergency | night_shift |
| `--slow` | Slow motion for recording | false |
| `--resume` | Load from checkpoint.json | false |
| `--test` | 50-step headless test | false |

## Output Files

| File | Description |
|---|---|
| `results_summary.json` | Full metrics, trajectories, robot summary |
| `heatmap.png` | Lane usage visualization (matplotlib) |
| `simulation.log` | Step-by-step event log |
| `checkpoint.json` | Latest saved simulation state |

## GUI Controls

### Both Modes
| Key | Action |
|---|---|
| `H` | Toggle heatmap overlay |
| `SPACE` | Pause / Resume |
| `↑↓←→` | Pan camera |
| `Q` | Quit |

### Manual Mode Only
| Key/Action | Effect |
|---|---|
| Click robot | Select it (white pulsing ring) |
| Click node | Assign as destination |
| `1`-`8` | Select robot R0-R7 directly |
| `ESC` | Deselect current robot |

## Reading the Sidebar

- **Step** — current simulation step
- **FPS** — rendering frame rate
- **Deadlocks** — total resolved deadlocks
- **Avg Delay** — average steps waited per robot
- **Throughput** — robots completed per step
- **Completed** — X/8, X/10, or X/12 depending on scenario
- Robot table — ID, status, speed bar, battery %
- Top Congestion — 4 most congested lanes with bars
- Throughput graph — last 50 steps history
