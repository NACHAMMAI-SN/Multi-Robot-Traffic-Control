import json

with open('results_summary.json') as f:
    data = json.load(f)

print(f"Total steps: {data['simulation_steps']}")
print(f"Completed: {data['robots_completed']}/8")
print(f"Deadlocks resolved: {data['metrics']['deadlocks_resolved']}")
print(f"Average delay: {data['metrics']['avg_delay_per_robot']}")
print(f"Throughput: {data['metrics']['throughput']}")
print("\nRobot completion details:")
for r in data['robot_summary']:
    print(f"  {r['id']}: goal_step={r['goal_reached_step']}, replans={r['replan_count']}, waiting={r['steps_waiting']}")
