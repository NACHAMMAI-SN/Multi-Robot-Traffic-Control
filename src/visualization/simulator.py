import pygame
import math
import networkx as nx


# Constants - IMPROVED VISIBILITY
WINDOW_W, WINDOW_H = 1400, 800
MAP_W = 950
BG = (15, 15, 35)
SIDEBAR_BG = (18, 18, 40)
TEXT_PRIMARY = (255, 255, 255)        # Pure white
TEXT_SECONDARY = (200, 200, 220)      # Light gray
TEXT_DIM = (150, 150, 180)            # Medium gray
DANGER = (255, 80, 80)
WARNING = (255, 200, 60)
SUCCESS = (80, 220, 120)
ACCENT = (120, 200, 255)              # Brighter blue
GOLD = (255, 200, 50)
ROBOT_COLORS = [
    (255, 100, 100), (100, 200, 255), (100, 255, 150), (255, 200, 80),
    (200, 100, 255), (255, 150, 50), (80, 255, 220), (255, 100, 200)
]


class Effect:
    def __init__(self, etype, pos, duration, color=(255, 255, 255)):
        self.type = etype
        self.pos = pos
        self.duration = duration
        self.max_dur = duration
        self.color = color
    
    @property
    def progress(self):
        return 1.0 - self.duration / self.max_dur
    
    def tick(self):
        self.duration -= 1
    
    @property
    def alive(self):
        return self.duration > 0


class Simulator:
    def __init__(self, lane_graph, robots, traffic_controller, heatmap, existing_screen=None, 
                 battery_manager=None, scenario="night_shift", max_steps=1000):
        self.fullscreen = True
        if existing_screen is None:
            pygame.init()
            self.screen = pygame.display.set_mode((WINDOW_W, WINDOW_H), pygame.FULLSCREEN)
            pygame.display.set_caption("Multi-Robot Traffic Control System")
        else:
            self.screen = existing_screen
        self.clock = pygame.time.Clock()
        self.lg = lane_graph
        self.robots = robots
        self.tc = traffic_controller
        self.hm = heatmap
        self.bm = battery_manager
        self.scenario = scenario
        self.max_steps = max_steps
        self.show_heatmap = False
        self.paused = False
        self.running = True
        self.effects = []
        self.cam = [30, 30]
        self.step_count = 0
        
        # INCREASED FONT SIZES
        self.f_large = pygame.font.SysFont("arial", 22, bold=True)
        self.f_med = pygame.font.SysFont("arial", 16, bold=True)
        self.f_small = pygame.font.SysFont("arial", 13)
        self.f_tiny = pygame.font.SysFont("arial", 11)
        
        # Manual mode attributes
        self.mode = "auto"
        self.selected_robot = None
        self.target_nodes = {}
        self.pulse_timer = 0
        self.notifications = []
        self.show_instructions = True
        self.instruction_timer = 300
        self.hover_robot = None
        self.hover_node = None
        self.assigned_robots = set()  # Track which robots got at least one assignment
        self.completed_trips = set()  # Robots that completed at least one trip
    
    def draw_text_shadow(self, surf, text, font, color, pos):
        """Draw text with shadow for better visibility."""
        shadow = font.render(text, True, (0, 0, 0))
        surf.blit(shadow, (pos[0] + 2, pos[1] + 2))
        main = font.render(text, True, color)
        surf.blit(main, pos)
    
    def show_menu_screen(self):
        """Show menu screen and return selected mode."""
        title_font = pygame.font.SysFont("arial", 48, bold=True)
        subtitle_font = pygame.font.SysFont("arial", 18)
        button_font = pygame.font.SysFont("arial", 28, bold=True)
        sub_font = pygame.font.SysFont("arial", 14)
        label_font = pygame.font.SysFont("arial", 12)
        
        left_button = pygame.Rect(200, 300, 400, 200)
        right_button = pygame.Rect(800, 300, 400, 200)
        
        while self.running:
            mouse_pos = pygame.mouse.get_pos()
            left_hover = left_button.collidepoint(mouse_pos)
            right_hover = right_button.collidepoint(mouse_pos)
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    return "auto"
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_q:
                        self.running = False
                        return "auto"
                    if event.key == pygame.K_1:
                        return "auto"
                    if event.key == pygame.K_2:
                        return "manual"
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if left_button.collidepoint(mouse_pos):
                        return "auto"
                    if right_button.collidepoint(mouse_pos):
                        return "manual"
            
            self.screen.fill(BG)
            
            title = title_font.render("Multi-Robot Traffic Control System", True, ACCENT)
            self.screen.blit(title, (WINDOW_W//2 - title.get_width()//2, 120))
            
            subtitle = subtitle_font.render("GOAT Robotics Hackathon", True, TEXT_SECONDARY)
            self.screen.blit(subtitle, (WINDOW_W//2 - subtitle.get_width()//2, 180))
            
            # Left button
            left_color = (40, 120, 70) if left_hover else (30, 80, 50)
            pygame.draw.rect(self.screen, left_color, left_button, border_radius=12)
            pygame.draw.rect(self.screen, (80, 220, 120), left_button, 3, border_radius=12)
            
            auto_text = button_font.render("AUTO MODE", True, (255, 255, 255))
            auto_sub = sub_font.render("Watch 8 robots navigate automatically", True, (200, 200, 200))
            auto_label = label_font.render("Press 1", True, (180, 180, 180))
            
            self.screen.blit(auto_text, (left_button.centerx - auto_text.get_width()//2, left_button.y + 60))
            self.screen.blit(auto_sub, (left_button.centerx - auto_sub.get_width()//2, left_button.y + 110))
            self.screen.blit(auto_label, (left_button.centerx - auto_label.get_width()//2, left_button.y + 160))
            
            # Right button
            right_color = (40, 70, 120) if right_hover else (30, 50, 80)
            pygame.draw.rect(self.screen, right_color, right_button, border_radius=12)
            pygame.draw.rect(self.screen, ACCENT, right_button, 3, border_radius=12)
            
            manual_text = button_font.render("MANUAL MODE", True, (255, 255, 255))
            manual_sub = sub_font.render("You control robot destinations", True, (200, 200, 200))
            manual_label = label_font.render("Press 2", True, (180, 180, 180))
            
            self.screen.blit(manual_text, (right_button.centerx - manual_text.get_width()//2, right_button.y + 60))
            self.screen.blit(manual_sub, (right_button.centerx - manual_sub.get_width()//2, right_button.y + 110))
            self.screen.blit(manual_label, (right_button.centerx - manual_label.get_width()//2, right_button.y + 160))
            
            # Bottom controls
            controls_y = 650
            controls = [("[1] Auto Mode", (80, 220, 120)), ("[2] Manual Mode", ACCENT), ("[Q] Quit", DANGER)]
            total_width = sum(label_font.size(text)[0] for text, _ in controls) + 40 * (len(controls) - 1)
            x = WINDOW_W//2 - total_width//2
            
            for text, color in controls:
                surf = pygame.Surface((label_font.size(text)[0] + 20, 30), pygame.SRCALPHA)
                pygame.draw.rect(surf, (*color, 80), (0, 0, surf.get_width(), 30), border_radius=6)
                t = label_font.render(text, True, (255, 255, 255))
                surf.blit(t, (10, 8))
                self.screen.blit(surf, (x, controls_y))
                x += surf.get_width() + 40
            
            pygame.display.flip()
            self.clock.tick(60)
        
        return "auto"
    
    def get_clicked_robot(self, mouse_pos):
        """Get robot at mouse position."""
        for robot in self.robots:
            try:
                rx, ry = robot.get_pixel_position()
                px, py = self.mpos(rx, ry)
                dist = ((mouse_pos[0]-px)**2 + (mouse_pos[1]-py)**2)**0.5
                if dist <= 17:
                    return robot
            except:
                pass
        return None
    
    def get_clicked_node(self, mouse_pos):
        """Get node at mouse position."""
        for node_id in self.lg.get_all_nodes():
            x, y = self.lg.get_node_position(node_id)
            px, py = self.mpos(x, y)
            dist = ((mouse_pos[0]-px)**2 + (mouse_pos[1]-py)**2)**0.5
            if dist <= 20:
                return node_id
        return None
    
    def get_hover_robot(self, mouse_pos):
        """Get robot being hovered."""
        return self.get_clicked_robot(mouse_pos)
    
    def get_hover_node(self, mouse_pos):
        """Get node being hovered."""
        return self.get_clicked_node(mouse_pos)
    
    def handle_manual_click(self, mouse_pos):
        """Handle manual mode click. Returns (action, data)."""
        clicked_robot = self.get_clicked_robot(mouse_pos)
        if clicked_robot:
            return ("select_robot", clicked_robot)
        if self.selected_robot:
            clicked_node = self.get_clicked_node(mouse_pos)
            if clicked_node is not None:
                return ("assign_goal", (self.selected_robot, clicked_node))
        return (None, None)
    
    def add_notification(self, text, color=None, duration=180):
        """Add a notification."""
        if color is None:
            color = SUCCESS
        self.notifications.append({
            "text": text,
            "color": color,
            "timer": duration,
            "max_timer": duration
        })
        if len(self.notifications) > 3:
            self.notifications.pop(0)
    
    def draw_notifications(self):
        """Draw notification system - IMPROVED VISIBILITY."""
        y = 15
        for notif in self.notifications[:]:
            notif["timer"] -= 1
            if notif["timer"] <= 0:
                self.notifications.remove(notif)
                continue
            alpha = min(255, int(255 * notif["timer"] / 60))
            surf = pygame.Surface((500, 42), pygame.SRCALPHA)  # Taller
            bg = (*notif["color"], min(230, alpha))  # More solid
            pygame.draw.rect(surf, bg, (0, 0, 500, 42), border_radius=8)
            txt = self.f_med.render(notif["text"], True, (255, 255, 255))  # f_med, pure white
            surf.blit(txt, (250 - txt.get_width()//2, 11))
            self.screen.blit(surf, (MAP_W//2 - 250, y))
            y += 48
    
    def draw_selected_robot_highlight(self, robot):
        """Draw highlight around selected robot."""
        try:
            rx, ry = robot.get_pixel_position()
            px, py = self.mpos(rx, ry)
            pygame.draw.circle(self.screen, (255, 255, 255), (px, py), 22, 3)
            pulse = abs(math.sin(self.pulse_timer * 0.05)) * 8
            pygame.draw.circle(self.screen, (255, 255, 100), (px, py), int(24 + pulse), 2)
        except:
            pass
    
    def draw_target_node(self, node_id):
        """Draw target node indicator."""
        x, y = self.lg.get_node_position(node_id)
        px, py = self.mpos(x, y)
        pulse = abs(math.sin(self.pulse_timer * 0.05)) * 6
        pygame.draw.circle(self.screen, (255, 220, 0), (px, py), int(18 + pulse), 3)
        lbl = self.f_small.render("TARGET", True, (255, 220, 0))
        self.screen.blit(lbl, (px - lbl.get_width()//2, py - 32))
    
    def draw_hover_tooltip(self, mouse_pos):
        """Draw hover tooltips."""
        mx, my = mouse_pos
        if self.hover_robot and self.mode == "manual":
            is_assigned = self.hover_robot.id in self.assigned_robots
            if self.selected_robot is None:
                if not is_assigned:
                    text = f"Click to select {self.hover_robot.id} (unassigned)"
                else:
                    text = f"Click to select {self.hover_robot.id}"
            else:
                text = f"Select {self.hover_robot.id}"
            surf = pygame.Surface((240, 28), pygame.SRCALPHA)
            pygame.draw.rect(surf, (40, 40, 80, 220), (0, 0, 240, 28), border_radius=6)
            t = self.f_small.render(text, True, (255, 255, 255))
            surf.blit(t, (120 - t.get_width()//2, 6))
            self.screen.blit(surf, (mx - 120, my - 38))
        elif self.hover_node is not None and self.mode == "manual" and self.selected_robot:
            text = f"Send {self.selected_robot.id} here → Node {self.hover_node}"
            surf = pygame.Surface((260, 28), pygame.SRCALPHA)
            pygame.draw.rect(surf, (40, 80, 40, 220), (0, 0, 260, 28), border_radius=6)
            t = self.f_small.render(text, True, (255, 255, 255))
            surf.blit(t, (130 - t.get_width()//2, 6))
            self.screen.blit(surf, (mx - 130, my - 38))
    
    def draw_path_preview(self, from_node, to_node):
        """Draw preview path when hovering over destination node."""
        try:
            preview_path = nx.astar_path(self.lg.graph, from_node, to_node, 
                                        weight=lambda u,v,d: self.lg.get_routing_weight(u,v))
            for i in range(len(preview_path)-1):
                n1x, n1y = self.lg.get_node_position(preview_path[i])
                n2x, n2y = self.lg.get_node_position(preview_path[i+1])
                p1 = self.mpos(n1x, n1y)
                p2 = self.mpos(n2x, n2y)
                for t in range(0, 10):
                    tx = int(p1[0] + (p2[0] - p1[0]) * t / 10)
                    ty = int(p1[1] + (p2[1] - p1[1]) * t / 10)
                    if t % 2 == 0:
                        pygame.draw.circle(self.screen, (255, 220, 0), (tx, ty), 3)
        except:
            pass
    
    def draw_hud_bar(self):
        """Draw HUD control bar at bottom - IMPROVED."""
        by = WINDOW_H - 30
        pygame.draw.rect(self.screen, (20, 20, 40), (0, by - 4, MAP_W, 34))
        
        if self.mode == "manual":
            controls = [
                ("SPACE", "Pause"), ("H", "Heatmap"), ("↑↓←→", "Pan"),
                ("1-8", "Select"), ("Click", "Assign"), ("ESC", "Deselect"), ("F11", "Fullscreen"), ("Q", "Quit")
            ]
        else:
            controls = [
                ("SPACE", "Pause"), ("H", "Heatmap"), ("↑↓←→", "Pan"), ("F11", "Fullscreen"), ("Q", "Quit")
            ]
        
        cx = 10
        for key, action in controls:
            ks = self.f_small.render(f"[{key}]", True, ACCENT)  # f_small
            as_ = self.f_small.render(action, True, TEXT_SECONDARY)
            pygame.draw.rect(self.screen, (30, 30, 55),
                           (cx - 2, by - 2, ks.get_width() + as_.get_width() + 16, 24),
                           border_radius=4)
            self.screen.blit(ks, (cx, by + 2))
            self.screen.blit(as_, (cx + ks.get_width() + 5, by + 2))
            cx += ks.get_width() + as_.get_width() + 22  # More spacing
    
    def draw_startup_tooltip(self):
        """Draw startup instruction tooltip."""
        if self.instruction_timer <= 0:
            return
        self.instruction_timer -= 1
        alpha = min(255, self.instruction_timer * 3)
        
        if self.mode == "auto":
            text = "Simulation running! Press H for heatmap  |  SPACE to pause"
        else:
            text = "MANUAL MODE: Click a robot to select, then click a node to assign goal"
        
        surf = pygame.Surface((700, 38), pygame.SRCALPHA)
        pygame.draw.rect(surf, (30, 30, 70, min(200, alpha)), (0, 0, 700, 38), border_radius=8)
        t = self.f_med.render(text, True, (255, 255, 255))
        surf.blit(t, (350 - t.get_width()//2, 10))
        self.screen.blit(surf, (MAP_W//2 - 350, 55))
    
    def draw_manual_instructions(self):
        """Draw manual mode instruction panel - IMPROVED VISIBILITY."""
        sx = MAP_W + 16
        y_start = WINDOW_H - 240  # Taller panel
        
        pygame.draw.rect(self.screen, (30, 30, 60, 240),  # More solid
                        (MAP_W + 8, y_start - 8, WINDOW_W - MAP_W - 16, 220),
                        border_radius=8)
        pygame.draw.rect(self.screen, (100, 100, 180),  # Brighter border
                        (MAP_W + 8, y_start - 8, WINDOW_W - MAP_W - 16, 220),
                        border_radius=8, width=2)
        
        y = y_start
        
        # Assignment progress
        from src.robots.robot import RobotStatus
        assigned_count = len(self.assigned_robots)
        total_robots = len(self.robots)
        progress_text = f"Assigned: {assigned_count}/{total_robots} robots"
        progress_surf = self.f_med.render(progress_text, True, ACCENT)
        self.screen.blit(progress_surf, (sx, y))
        y += 22
        
        # Robot checklist
        y += 4
        for i, robot in enumerate(self.robots):
            if robot.id in self.completed_trips:
                dot_color = GOLD  # Gold for completed trips
                status = "✓"
            elif robot.id in self.assigned_robots:
                dot_color = SUCCESS  # Green for assigned
                status = "✓"
            else:
                dot_color = DANGER  # Red for unassigned
                status = "●"
            
            # Draw status dot
            pygame.draw.circle(self.screen, dot_color, (sx + 6, y + 7), 4)
            
            # Draw robot info
            if robot.id in self.target_nodes:
                text = f"{robot.id} → Node {self.target_nodes[robot.id]}"
                color = SUCCESS
            elif robot.id in self.completed_trips:
                text = f"{robot.id} completed!"
                color = GOLD
            elif robot.id in self.assigned_robots:
                text = f"{robot.id} moving"
                color = TEXT_PRIMARY
            else:
                text = f"{robot.id} not assigned"
                color = TEXT_DIM
            
            txt = self.f_small.render(text, True, color)
            self.screen.blit(txt, (sx + 18, y))
            y += 18
        
        # Add deadlock demo hint
        y += 8
        hint1 = self.f_tiny.render("💡 TIP: Assign robots toward each other", True, TEXT_DIM)
        hint2 = self.f_tiny.render("    to see deadlock resolution!", True, TEXT_DIM)
        self.screen.blit(hint1, (sx, y))
        self.screen.blit(hint2, (sx, y + 12))
    
    def mpos(self, x, y):
        """Map position to screen coordinates."""
        return (int(x + self.cam[0]), int(y + self.cam[1]))
    
    def draw_lane(self, u, v):
        """Draw a lane between two nodes."""
        ux, uy = self.lg.get_node_position(u)
        vx, vy = self.lg.get_node_position(v)
        p1 = self.mpos(ux, uy)
        p2 = self.mpos(vx, vy)
        meta = self.lg.get_lane_metadata(u, v)
        if not meta:
            return
        
        if self.show_heatmap:
            color = self.hm.get_heatmap_color(u, v)
            width = 5
        else:
            lt = meta.get('lane_type')
            sl = meta.get('safety_level')
            sl_val = sl.value if sl else 1
            if sl_val >= 4:
                color = (180, 60, 255)
                width = 3
            elif lt and lt.name == 'HUMAN_ZONE':
                color = (255, 180, 60)
                width = 2
            elif lt and lt.name == 'NARROW':
                color = (60, 140, 255)
                width = 1
            elif lt and lt.name == 'INTERSECTION':
                color = (60, 220, 180)
                width = 3
            else:
                color = (55, 55, 90)
                width = 2
        
        pygame.draw.line(self.screen, color, p1, p2, width)
        
        # Draw arrow
        ax = p1[0] + (p2[0] - p1[0]) * 0.65
        ay = p1[1] + (p2[1] - p1[1]) * 0.65
        angle = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
        s = 7
        tip = (ax + math.cos(angle) * s, ay + math.sin(angle) * s)
        left = (ax + math.cos(angle + 2.4) * s * 0.6, ay + math.sin(angle + 2.4) * s * 0.6)
        right = (ax + math.cos(angle - 2.4) * s * 0.6, ay + math.sin(angle - 2.4) * s * 0.6)
        pygame.draw.polygon(self.screen, color, [tip, left, right])
    
    def draw_node(self, node_id):
        """Draw a node - IMPROVED TEXT."""
        x, y = self.lg.get_node_position(node_id)
        px, py = self.mpos(x, y)
        
        # Check if this is a charging station
        is_charger = self.bm and node_id in self.bm.charging_stations if self.bm else False
        
        if is_charger:
            # Draw charging station with yellow ring
            pygame.draw.circle(self.screen, (40, 40, 70), (px, py), 14)
            pygame.draw.circle(self.screen, (255, 220, 0), (px, py), 18, 2)
            label = self.f_small.render(str(node_id), True, TEXT_SECONDARY)
            self.screen.blit(label, (px - label.get_width() // 2, py - label.get_height() // 2))
            cs_lbl = self.f_tiny.render("CHG", True, (255, 220, 0))
            self.screen.blit(cs_lbl, (px - cs_lbl.get_width() // 2, py + 16))
        else:
            pygame.draw.circle(self.screen, (40, 40, 70), (px, py), 14)
            pygame.draw.circle(self.screen, (80, 80, 130), (px, py), 14, 2)
            label = self.f_small.render(str(node_id), True, TEXT_SECONDARY)
            self.screen.blit(label, (px - label.get_width() // 2, py - label.get_height() // 2))
    
    def draw_robot(self, robot, idx):
        """Draw a robot with effects - IMPROVED."""
        try:
            rx, ry = robot.get_pixel_position()
            px, py = self.mpos(rx, ry)
            color = ROBOT_COLORS[idx % len(ROBOT_COLORS)]
            
            # Draw RED DASHED ring for unassigned robots in manual mode
            from src.robots.robot import RobotStatus
            if self.mode == "manual" and robot.id not in self.assigned_robots:
                if robot.status == RobotStatus.IDLE:
                    # Dashed ring
                    for angle in range(0, 360, 30):
                        rad = math.radians(angle)
                        x1 = px + math.cos(rad) * 20
                        y1 = py + math.sin(rad) * 20
                        x2 = px + math.cos(rad + math.radians(20)) * 20
                        y2 = py + math.sin(rad + math.radians(20)) * 20
                        pygame.draw.line(self.screen, (180, 50, 50), (x1, y1), (x2, y2), 2)
            
            # Draw glow
            glow = pygame.Surface((60, 60), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*color, 40), (30, 30), 28)
            self.screen.blit(glow, (px - 30, py - 30))
            
            # Draw robot with status ring
            ring_map = {
                RobotStatus.MOVING: SUCCESS,
                RobotStatus.WAITING: WARNING,
                RobotStatus.EMERGENCY_STOP: DANGER,
                RobotStatus.GOAL_REACHED: (200, 200, 200),
                RobotStatus.IDLE: TEXT_DIM
            }
            ring = ring_map.get(robot.status, TEXT_SECONDARY)
            pygame.draw.circle(self.screen, ring, (px, py), 17)
            pygame.draw.circle(self.screen, color, (px, py), 14)
            
            lbl = self.f_small.render(str(robot.id), True, (15, 15, 35))
            self.screen.blit(lbl, (px - lbl.get_width() // 2, py - lbl.get_height() // 2))
            
            # Emergency indicator
            if robot.emergency_flash_timer > 0:
                bang = self.f_large.render("!", True, DANGER)
                self.screen.blit(bang, (px - 4, py - 34))
            
            # Draw path preview
            if robot.path and robot.path_index < len(robot.path) - 1:
                for i in range(robot.path_index, min(robot.path_index + 6, len(robot.path) - 1)):
                    nx1, ny1 = self.lg.get_node_position(robot.path[i])
                    nx2, ny2 = self.lg.get_node_position(robot.path[i + 1])
                    sp1 = self.mpos(nx1, ny1)
                    sp2 = self.mpos(nx2, ny2)
                    for t in range(1, 5):
                        dx = int(sp1[0] + (sp2[0] - sp1[0]) * t / 5)
                        dy = int(sp1[1] + (sp2[1] - sp1[1]) * t / 5)
                        pygame.draw.circle(self.screen, color, (dx, dy), 2)
            
            # Draw battery bar below robot
            if self.bm:
                bat = self.bm.batteries.get(robot.id, 100.0)
                bar_w = 30
                bar_h = 5
                bx = px - bar_w // 2
                by = py + 20
                # Background
                pygame.draw.rect(self.screen, (40, 40, 40), (bx, by, bar_w, bar_h))
                # Fill
                fill = int(bar_w * bat / 100)
                bat_color = self.bm.get_battery_color(robot.id)
                if fill > 0:
                    pygame.draw.rect(self.screen, bat_color, (bx, by, fill, bar_h))
                # Critical flash
                if bat <= 10:
                    bolt = self.f_tiny.render("⚡", True, (255, 200, 0))
                    self.screen.blit(bolt, (px - 6, py - 38))
                # Charging indicator
                if self.bm.is_charging(robot.id):
                    chg = self.f_tiny.render("CHG", True, (80, 220, 120))
                    self.screen.blit(chg, (px - chg.get_width() // 2, py - 38))
        except Exception:
            pass
    
    def draw_effects(self):
        """Draw visual effects."""
        for eff in self.effects[:]:
            eff.tick()
            if not eff.alive:
                self.effects.remove(eff)
                continue
            try:
                px, py = self.mpos(*eff.pos)
                p = eff.progress
                alpha = int(255 * (1 - p))
                
                if eff.type == "goal":
                    for rm in [1.0, 1.6, 2.2]:
                        r = int(20 + 40 * p * rm)
                        s = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
                        a = max(0, int(alpha * (1 - (rm - 1) / 1.5)))
                        pygame.draw.circle(s, (*SUCCESS, a), (r + 2, r + 2), r, 2)
                        self.screen.blit(s, (px - r - 2, py - r - 2))
                elif eff.type == "emergency":
                    s = pygame.Surface((60, 28), pygame.SRCALPHA)
                    pygame.draw.rect(s, (*DANGER, alpha), (0, 0, 60, 28), border_radius=5)
                    t = self.f_small.render("STOP!", True, (255, 255, 255))
                    s.blit(t, (4, 6))
                    self.screen.blit(s, (px - 30, py - 44))
                elif eff.type == "deadlock":
                    s = pygame.Surface((90, 28), pygame.SRCALPHA)
                    pygame.draw.rect(s, (*DANGER, alpha), (0, 0, 90, 28), border_radius=5)
                    t = self.f_small.render("DEADLOCK!", True, (255, 255, 255))
                    s.blit(t, (4, 6))
                    self.screen.blit(s, (px - 45, py - 40))
            except Exception:
                pass
    
    def add_effect(self, etype, node_id, duration=60):
        """Add a visual effect at a node."""
        pos = self.lg.get_node_position(node_id)
        self.effects.append(Effect(etype, pos, duration))
    
    def draw_bar(self, x, y, w, h, value, max_val, color):
        """Draw a progress bar."""
        pygame.draw.rect(self.screen, (40, 40, 60), (x, y, w, h), border_radius=3)
        fill = int(w * min(value / max(max_val, 0.001), 1.0))
        if fill > 0:
            pygame.draw.rect(self.screen, color, (x, y, fill, h), border_radius=3)
    
    def draw_sidebar(self):
        """Draw the information sidebar - IMPROVED VISIBILITY."""
        sx = MAP_W
        pygame.draw.rect(self.screen, SIDEBAR_BG, (sx, 0, WINDOW_W - sx, WINDOW_H))
        pygame.draw.line(self.screen, (50, 50, 80), (sx, 0), (sx, WINDOW_H), 2)
        
        x = sx + 16
        y = 14
        
        # MODE BANNER - IMPROVED
        banner_h = 40
        if self.mode == "manual":
            banner_bg = (140, 100, 20)  # Bright yellow bg
            banner_text = "🎮 MANUAL MODE"
        else:
            banner_bg = (40, 140, 60)  # Bright green bg
            banner_text = "🤖 AUTO MODE"
        
        banner = self.f_large.render(banner_text, True, (255, 255, 255))  # Pure white
        banner_width = banner.get_width() + 40
        pygame.draw.rect(self.screen, banner_bg, 
                        (sx + WINDOW_W - MAP_W - banner_width - 10, y, banner_width, banner_h),
                        border_radius=8)
        self.screen.blit(banner, (sx + WINDOW_W - MAP_W - banner_width + 20, y + 8))
        y += banner_h + 8
        
        # Title
        title = self.f_large.render("Traffic Control", True, ACCENT)
        self.screen.blit(title, (x, y))
        y += 26
        sub = self.f_small.render("Multi-Robot System", True, TEXT_SECONDARY)
        self.screen.blit(sub, (x, y))
        y += 20
        pygame.draw.line(self.screen, (50, 50, 80), (sx + 10, y), (WINDOW_W - 10, y))
        y += 10
        
        # Metrics - IMPROVED TEXT
        metrics = self.tc.get_metrics()
        total = len(self.robots)
        completed = min(metrics.get('robots_completed', 0), total)
        
        for label, val in [
            ("Step", str(self.step_count)),
            ("FPS", str(int(self.clock.get_fps()))),
            ("Deadlocks", str(metrics['deadlocks_resolved'])),
            ("Avg Delay", f"{metrics['avg_delay_per_robot']:.1f}"),
            ("Throughput", f"{metrics['throughput']:.4f}"),
            ("Completed", f"{completed}/{total}"),
        ]:
            self.screen.blit(self.f_small.render(label, True, TEXT_SECONDARY), (x, y))
            vs = self.f_small.render(val, True, TEXT_PRIMARY)
            self.screen.blit(vs, (WINDOW_W - vs.get_width() - 16, y))
            y += 18
        
        y += 6
        pygame.draw.line(self.screen, (50, 50, 80), (sx + 10, y), (WINDOW_W - 10, y))
        y += 10
        
        # Robots - TALLER SPACING
        self.screen.blit(self.f_med.render("ROBOTS", True, TEXT_SECONDARY), (x, y))
        y += 20
        from src.robots.robot import RobotStatus
        for i, robot in enumerate(self.robots):
            color = ROBOT_COLORS[i % len(ROBOT_COLORS)]
            pygame.draw.circle(self.screen, color, (x + 8, y + 9), 7)
            self.screen.blit(self.f_med.render(str(robot.id), True, TEXT_PRIMARY), (x + 20, y))  # f_med
            st_map = {
                RobotStatus.MOVING: ("MOV", SUCCESS),
                RobotStatus.WAITING: ("WAI", WARNING),
                RobotStatus.EMERGENCY_STOP: ("STP", DANGER),
                RobotStatus.GOAL_REACHED: ("DONE", (200, 200, 200)),
                RobotStatus.IDLE: ("IDLE", TEXT_DIM)
            }
            st, sc = st_map.get(robot.status, ("???", TEXT_SECONDARY))
            self.screen.blit(self.f_small.render(st, True, sc), (x + 70, y))
            self.draw_bar(x + 110, y + 2, 200, 14, robot.current_speed, robot.base_speed, color)  # Speed bar
            # Battery percentage
            if self.bm:
                bat_pct = f"{int(self.bm.batteries[robot.id])}%"
                bat_color = self.bm.get_battery_color(robot.id)
                bat_s = self.f_tiny.render(bat_pct, True, bat_color)
                self.screen.blit(bat_s, (x + 320, y + 2))
            y += 24  # More spacing
        
        y += 6
        pygame.draw.line(self.screen, (50, 50, 80), (sx + 10, y), (WINDOW_W - 10, y))
        y += 10
        
        # Congestion hotspots
        self.screen.blit(self.f_med.render("TOP CONGESTION", True, TEXT_SECONDARY), (x, y))
        y += 20
        for u, v, score in self.hm.get_congestion_hotspots()[:4]:
            self.screen.blit(self.f_small.render(f"Lane {u}→{v}", True, TEXT_PRIMARY), (x, y))
            self.draw_bar(x + 90, y + 2, 200, 12, score, 1.0, self.hm.get_heatmap_color(u, v))
            self.screen.blit(self.f_tiny.render(f"{score:.2f}", True, TEXT_SECONDARY), (x + 296, y))
            y += 19
        
        y += 6
        pygame.draw.line(self.screen, (50, 50, 80), (sx + 10, y), (WINDOW_W - 10, y))
        y += 10
        
        # Throughput graph
        self.screen.blit(self.f_med.render("THROUGHPUT", True, TEXT_SECONDARY), (x, y))
        y += 18
        gh, gw = 55, 390
        pygame.draw.rect(self.screen, (28, 28, 50), (x, y, gw, gh), border_radius=4)
        hist = self.tc.throughput_history[-50:]
        if len(hist) >= 2:
            mv = max(max(hist), 1)
            pts = [(x + int(i * gw / (len(hist) - 1)), y + gh - int(hist[i] / mv * (gh - 4)) - 2)
                   for i in range(len(hist))]
            pygame.draw.lines(self.screen, ACCENT, False, pts, 2)
        
        y += gh + 8
        
        # Manual mode deadlock demo button
        if self.mode == "manual":
            btn_rect = pygame.Rect(MAP_W+16, y, WINDOW_W-MAP_W-32, 30)
            hover = btn_rect.collidepoint(pygame.mouse.get_pos())
            color = (180,50,50) if hover else (120,30,30)
            pygame.draw.rect(self.screen, color, btn_rect, border_radius=6)
            btn_txt = self.f_small.render("Force Deadlock Demo", True, (255,255,255))
            self.screen.blit(btn_txt, (btn_rect.centerx - btn_txt.get_width()//2, btn_rect.y + 7))
            self.deadlock_demo_btn = btn_rect
            y += 38
        
        # Manual mode instructions OR auto mode legend
        if self.mode == "manual":
            self.draw_manual_instructions()
        else:
            pygame.draw.line(self.screen, (50, 50, 80), (sx + 10, y), (WINDOW_W - 10, y))
            y += 8
            self.screen.blit(self.f_med.render("LANE LEGEND", True, TEXT_SECONDARY), (x, y))
            y += 18
            for col, name in [
                ((180, 60, 255), "Critical"),
                ((255, 180, 60), "Human Zone"),
                ((60, 140, 255), "Narrow"),
                ((60, 220, 180), "Intersection"),
                ((55, 55, 90), "Normal")
            ]:
                pygame.draw.rect(self.screen, col, (x, y + 3, 22, 8), border_radius=2)
                self.screen.blit(self.f_tiny.render(name, True, TEXT_SECONDARY), (x + 28, y))
                y += 16
    
    def draw_map_panel(self):
        """Draw the main map panel."""
        pygame.draw.rect(self.screen, BG, (0, 0, MAP_W, WINDOW_H))
        
        # Draw lanes
        for u, v in self.lg.get_all_edges():
            self.draw_lane(u, v)
        
        # Draw nodes
        for nid in self.lg.get_all_nodes():
            self.draw_node(nid)
        
        # Draw robots
        for i, robot in enumerate(self.robots):
            self.draw_robot(robot, i)
        
        # Draw effects
        self.draw_effects()
        
        # Emergency countdown timer
        if self.scenario == "emergency":
            remaining = max(0, self.max_steps - self.step_count)
            color = SUCCESS if remaining > 100 else \
                    WARNING if remaining > 50 else DANGER
            timer_txt = self.f_large.render(
                f"⏱ {remaining} steps remaining", True, color)
            # Draw with shadow
            shadow = self.f_large.render(
                f"⏱ {remaining} steps remaining", True, (0, 0, 0))
            self.screen.blit(shadow, (MAP_W // 2 -
                timer_txt.get_width() // 2 + 2, 12))
            self.screen.blit(timer_txt, (MAP_W // 2 -
                timer_txt.get_width() // 2, 10))
            # Flash red background when < 50 steps
            if remaining < 50:
                flash = pygame.Surface((MAP_W, WINDOW_H), pygame.SRCALPHA)
                alpha = int(40 * abs(math.sin(self.pulse_timer * 0.1)))
                pygame.draw.rect(flash, (255, 0, 0, alpha),
                                (0, 0, MAP_W, WINDOW_H))
                self.screen.blit(flash, (0, 0))
        
        # Manual mode elements
        self.pulse_timer += 1
        
        # Draw selected robot highlight
        if self.selected_robot:
            self.draw_selected_robot_highlight(self.selected_robot)
        
        # Draw target nodes
        for robot_id, node_id in self.target_nodes.items():
            self.draw_target_node(node_id)
        
        # Draw hover tooltip and path preview
        mouse_pos = pygame.mouse.get_pos()
        if mouse_pos[0] < MAP_W:
            self.hover_robot = self.get_hover_robot(mouse_pos)
            self.hover_node = self.get_hover_node(mouse_pos)
            
            # Draw path preview when hovering over node with robot selected
            if self.mode == "manual" and self.selected_robot and self.hover_node is not None:
                self.draw_path_preview(self.selected_robot.current_node, self.hover_node)
            
            self.draw_hover_tooltip(mouse_pos)
        
        # Draw startup tooltip
        self.draw_startup_tooltip()
        
        # Draw notifications
        self.draw_notifications()
        
        # Draw HUD bar
        self.draw_hud_bar()
        
        # Indicators
        if self.show_heatmap:
            ind = self.f_med.render("HEATMAP ON", True, WARNING)
            self.screen.blit(ind, (10, 10))
        
        st = "⏸ PAUSED" if self.paused else "▶ RUNNING"
        sc = WARNING if self.paused else SUCCESS
        self.screen.blit(self.f_med.render(st, True, sc), (10, WINDOW_H - 60))
    
    def handle_events(self):
        """Handle pygame events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F11:
                    self.fullscreen = not self.fullscreen
                    if self.fullscreen:
                        self.screen = pygame.display.set_mode(
                            (WINDOW_W, WINDOW_H), pygame.FULLSCREEN)
                    else:
                        self.screen = pygame.display.set_mode(
                            (WINDOW_W, WINDOW_H))
                if event.key == pygame.K_q:
                    self.running = False
                    return False
                if event.key == pygame.K_SPACE:
                    self.paused = not self.paused
                if event.key == pygame.K_h:
                    self.show_heatmap = not self.show_heatmap
                if event.key == pygame.K_UP:
                    self.cam[1] += 20
                if event.key == pygame.K_DOWN:
                    self.cam[1] -= 20
                if event.key == pygame.K_LEFT:
                    self.cam[0] += 20
                if event.key == pygame.K_RIGHT:
                    self.cam[0] -= 20
                if event.key == pygame.K_ESCAPE:
                    self.selected_robot = None
                if self.mode == "manual":
                    for i in range(8):
                        key_attr = f"K_{i+1}"
                        if hasattr(pygame, key_attr):
                            if event.key == getattr(pygame, key_attr) and i < len(self.robots):
                                self.selected_robot = self.robots[i]
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.mode == "manual" and hasattr(self, 'deadlock_demo_btn'):
                    if self.deadlock_demo_btn.collidepoint(event.pos):
                        self.trigger_deadlock_demo = True
        return True
    
    def render(self):
        """Render the frame."""
        self.screen.fill(BG)
        self.draw_map_panel()
        self.draw_sidebar()
        pygame.display.flip()
    
    def tick(self):
        """Execute one tick of the simulator."""
        if not self.handle_events():
            return False
        self.render()
        self.clock.tick(60)
        return not self.paused
    
    def update_step(self, step):
        """Update step counter."""
        self.step_count = step
    
    def show_post_round_screen(self, played_mode, metrics):
        """Show post-round selection screen. Returns 'auto', 'manual', or 'quit'."""
        clock = pygame.time.Clock()
        
        # Button definitions
        btn_auto   = pygame.Rect(150, 420, 320, 140)
        btn_manual = pygame.Rect(540, 420, 320, 140)
        btn_quit   = pygame.Rect(930, 420, 320, 140)
        
        while True:
            mouse_pos = pygame.mouse.get_pos()
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "quit"
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_1: return "auto"
                    if event.key == pygame.K_2: return "manual"
                    if event.key in (pygame.K_3, pygame.K_q): return "quit"
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if btn_auto.collidepoint(mouse_pos):   return "auto"
                    if btn_manual.collidepoint(mouse_pos): return "manual"
                    if btn_quit.collidepoint(mouse_pos):   return "quit"
            
            # Background
            self.screen.fill((15, 15, 35))
            
            # Title
            title = self.f_large.render("ROUND COMPLETE! 🎉", True, SUCCESS)
            self.screen.blit(title, (WINDOW_W//2 - title.get_width()//2, 60))
            
            # Mode played
            mode_txt = self.f_med.render(
                f"You played: {'AUTO MODE' if played_mode=='auto' else 'MANUAL MODE'}",
                True, ACCENT)
            self.screen.blit(mode_txt, (WINDOW_W//2 - mode_txt.get_width()//2, 110))
            
            # Stats box
            stats_box = pygame.Rect(WINDOW_W//2 - 220, 150, 440, 200)
            pygame.draw.rect(self.screen, (25,25,55), stats_box, border_radius=12)
            pygame.draw.rect(self.screen, (60,60,100), stats_box, border_radius=12, width=2)
            
            total = len(self.robots)
            completed = min(metrics.get('robots_completed', 0), total)
            
            stats = [
                ("Steps",      str(metrics.get("total_steps", 0))),
                ("Completed",  f"{completed}/{total}"),
                ("Deadlocks",  str(metrics.get("deadlocks_resolved", 0))),
                ("Avg Delay",  f"{metrics.get('avg_delay_per_robot', 0):.1f}"),
                ("Throughput", f"{metrics.get('throughput', 0):.4f}"),
            ]
            sy = 170
            for label, val in stats:
                lbl_s = self.f_small.render(label, True, TEXT_SECONDARY)
                val_s = self.f_small.render(val,   True, TEXT_PRIMARY)
                self.screen.blit(lbl_s, (WINDOW_W//2 - 200, sy))
                self.screen.blit(val_s, (WINDOW_W//2 + 80,  sy))
                sy += 30
            
            # Question
            q_txt = self.f_large.render("What do you want to do next?", True, TEXT_PRIMARY)
            self.screen.blit(q_txt, (WINDOW_W//2 - q_txt.get_width()//2, 370))
            
            # Draw buttons
            buttons = [
                (btn_auto,   "AUTO MODE",   "Watch robots navigate",    SUCCESS, "1"),
                (btn_manual, "MANUAL MODE", "Control robots yourself",  ACCENT,  "2"),
                (btn_quit,   "QUIT",        "Exit simulation",          DANGER,  "3"),
            ]
            for rect, label, sublabel, color, key in buttons:
                hover = rect.collidepoint(mouse_pos)
                bg = tuple(min(255, c+30) for c in color) if hover else color
                # Button background
                dark_bg = tuple(max(0, c//4) for c in color)
                pygame.draw.rect(self.screen, dark_bg, rect, border_radius=12)
                pygame.draw.rect(self.screen, bg, rect, border_radius=12, width=3)
                # Button text
                lbl = self.f_large.render(label, True, (255,255,255))
                sub = self.f_small.render(sublabel, True, (200,200,220))
                key_s = self.f_med.render(f"[{key}]", True, bg)
                self.screen.blit(lbl,   (rect.centerx - lbl.get_width()//2,   rect.y + 22))
                self.screen.blit(sub,   (rect.centerx - sub.get_width()//2,   rect.y + 62))
                self.screen.blit(key_s, (rect.centerx - key_s.get_width()//2, rect.y + 95))
            
            pygame.display.flip()
            clock.tick(60)
    
    def shutdown(self):
        """Shutdown pygame."""
        pygame.quit()
