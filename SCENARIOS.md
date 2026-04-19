# Scenarios

**Last Updated:** April 19, 2026

## Overview

Three unique scenarios test different aspects of the traffic 
control system. Each modifies the lane graph and robot 
configuration differently.

## 🌙 Night Shift

**Robots:** 8 | **Time Limit:** 800 steps

### What changes
- 4 maintenance lanes closed (weight=99999, effectively blocked)
- All lane speeds reduced by 30%
- All HUMAN_ZONE lanes upgraded to CRITICAL safety level

### What it tests
- Pathfinding around blocked routes
- Speed-limited navigation
- Conservative safety enforcement

### Start → Goal pairs
R0:0→19, R1:1→18, R2:2→17, R3:3→16,
R4:4→15, R5:5→14, R6:6→13, R7:7→12

---

## ⚡ Peak Hours

**Robots:** 12 | **Time Limit:** 1000 steps

### What changes
- All lanes start pre-congested (congestion_score=0.35)
- INTERSECTION lanes limited to capacity=1 (single robot only)
- 4 extra robots added (12 total)

### What it tests
- High-traffic deadlock resolution
- Intersection bottleneck handling
- System scalability (12 robots vs 8)

### Start → Goal pairs
Standard 8 + R8:8→11, R9:9→10, R10:0→14, R11:1→13

---

## 🚨 Emergency Evacuation

**Robots:** 10 | **Time Limit:** 300 steps (tight countdown!)

### What changes
- All robot goals redirected to safe zones: nodes 16, 17, 18, 19
- NORMAL lane speeds boosted by 50%
- Countdown timer displayed at top of screen
- Screen flashes red when <50 steps remain

### What it tests
- Urgent replanning to new destinations
- High-speed routing on boosted lanes
- Time-pressure performance

### Safe zone assignment
Robots distributed evenly: R0→16, R1→17, R2→18, R3→19, 
R4→16, R5→17, R6→18, R7→19, R8→16, R9→17

---

## Checkpoint & Resume

All scenarios support checkpoint/resume:
- Checkpoint auto-saved every 50 steps
- Saves robot positions, battery, heatmap state
- Resume any scenario with `--resume` flag
