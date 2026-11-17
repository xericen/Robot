from __future__ import annotations

import pygame


COLORS = {
    "background": (238, 242, 244), "panel": (255, 255, 255), "text": (31, 41, 55),
    "muted": (100, 116, 139), "robot": (37, 99, 235), "worker": (249, 115, 22),
    "obstacle": (107, 114, 128), "goal": (22, 163, 74), "danger": (220, 38, 38),
    "path": (96, 165, 250), "accent": (15, 118, 110),
}


class DashboardRenderer:
    def __init__(self, screen: pygame.Surface) -> None:
        self.screen = screen
        self.font = pygame.font.SysFont("arial", 16)
        self.small = pygame.font.SysFont("arial", 13)
        self.title = pygame.font.SysFont("arial", 24, bold=True)
        self.world_rect = pygame.Rect(220, 56, 780, 560)

    def world_point(self, simulation, point) -> tuple[int, int]:
        x = self.world_rect.left + point[0] / simulation.scenario.width * self.world_rect.width
        y = self.world_rect.bottom - point[1] / simulation.scenario.height * self.world_rect.height
        return int(x), int(y)

    def draw(self, simulation, paused: bool, show_path: bool, show_safety: bool, show_risk: bool,
             speed_multiplier: float, buttons: list[tuple[str, pygame.Rect]]) -> None:
        self.screen.fill(COLORS["background"])
        pygame.draw.rect(self.screen, COLORS["panel"], self.world_rect)
        for obstacle in simulation.scenario.obstacles:
            x, y, width, height = obstacle
            left, bottom = self.world_point(simulation, (x, y))
            right, top = self.world_point(simulation, (x + width, y + height))
            pygame.draw.rect(self.screen, COLORS["obstacle"], pygame.Rect(left, top, right - left, bottom - top))
        if show_path and simulation.robot.path:
            pygame.draw.lines(self.screen, (148, 163, 184), False,
                              [self.world_point(simulation, point) for point in simulation.robot.path], 2)
        if len(simulation.robot.trajectory) > 1:
            pygame.draw.lines(self.screen, COLORS["path"], False,
                              [self.world_point(simulation, point) for point in simulation.robot.trajectory], 2)
        goal = self.world_point(simulation, simulation.robot.goal)
        pygame.draw.circle(self.screen, COLORS["goal"], goal, 12, 3)
        scale = self.world_rect.width / simulation.scenario.width
        for agent in simulation.agents:
            point = self.world_point(simulation, agent.position)
            color = COLORS["worker"] if agent.kind == "worker" else (124, 58, 237)
            if show_safety:
                pygame.draw.circle(self.screen, (*color, 45), point, int((agent.radius + simulation.safety_distance) * scale), 1)
            pygame.draw.circle(self.screen, color, point, max(4, int(agent.radius * scale)))
        robot_point = self.world_point(simulation, simulation.robot.position)
        if show_safety:
            pygame.draw.circle(self.screen, COLORS["robot"], robot_point,
                               int((simulation.robot.radius + simulation.safety_distance) * scale), 1)
        if show_risk:
            for agent in simulation.agents:
                distance = float(((agent.position - simulation.robot.position) ** 2).sum() ** 0.5)
                if distance < simulation.robot.radius + agent.radius + simulation.safety_distance:
                    pygame.draw.line(self.screen, COLORS["danger"], robot_point, self.world_point(simulation, agent.position), 3)
        pygame.draw.circle(self.screen, COLORS["robot"], robot_point, max(7, int(simulation.robot.radius * scale)))
        self._panels(simulation, paused, speed_multiplier, buttons)

    def _panels(self, simulation, paused: bool, speed_multiplier: float,
                buttons: list[tuple[str, pygame.Rect]]) -> None:
        self.screen.blit(self.title.render("Warehouse Simulator", True, COLORS["text"]), (24, 18))
        labels = [
            f"Algorithm  {simulation.algorithm.name}", f"Scenario   {simulation.scenario_name}",
            f"Agents     {simulation.agent_count}", f"Seed       {simulation.seed}",
            f"State      {'PAUSED' if paused else simulation.robot.status.upper()}",
            f"Physics    {simulation.elapsed:6.1f} s", f"Speed      {speed_multiplier:.1f}x",
            f"Collisions {simulation.metrics.collision_count}",
            f"Violations {simulation.metrics.safety_violations}",
            f"Min sep.   {simulation.metrics.minimum_separation if simulation.metrics.minimum_separation < 999 else 0:.2f} m",
        ]
        pygame.draw.rect(self.screen, COLORS["panel"], pygame.Rect(20, 56, 180, 560))
        for index, label in enumerate(labels):
            self.screen.blit(self.small.render(label, True, COLORS["text"]), (36, 82 + index * 31))
        pygame.draw.rect(self.screen, COLORS["panel"], pygame.Rect(1020, 56, 240, 560))
        self.screen.blit(self.font.render("Controls", True, COLORS["text"]), (1040, 78))
        for label, rect in buttons:
            active = label.lower() == simulation.algorithm_name
            pygame.draw.rect(self.screen, COLORS["accent"] if active else (241, 245, 249), rect, border_radius=5)
            text = self.small.render(label, True, (255, 255, 255) if active else COLORS["text"])
            self.screen.blit(text, text.get_rect(center=rect.center))
        hints = ["SPACE start/pause", "R reset", "UP/DOWN agents", "[ / ] simulation speed",
                 "P path · S safety · C risk", "ESC quit"]
        for index, hint in enumerate(hints):
            self.screen.blit(self.small.render(hint, True, COLORS["muted"]), (1040, 456 + index * 24))
