from __future__ import annotations

import argparse
import os

import pygame

from simulator.environment import WarehouseSimulation
from simulator.rendering import DashboardRenderer


AGENT_COUNTS = [5, 10, 20, 40, 80]


def create_simulation(algorithm: str, count: int, seed: int, scenario: str) -> WarehouseSimulation:
    return WarehouseSimulation(scenario, algorithm, count, seed)


def run_ui(algorithm: str, count: int, seed: int, scenario: str, headless_steps: int = 0) -> int:
    if headless_steps:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    pygame.init()
    screen = pygame.display.set_mode((1280, 680))
    pygame.display.set_caption("Warehouse Collision Avoidance Simulator")
    clock = pygame.time.Clock()
    simulation = create_simulation(algorithm, count, seed, scenario)
    renderer = DashboardRenderer(screen)
    paused, running = False, True
    show_path = show_safety = show_risk = True
    speed_multiplier = 1.0
    buttons = [
        ("naive", pygame.Rect(1040, 120, 62, 34)), ("vo", pygame.Rect(1110, 120, 62, 34)),
        ("orca", pygame.Rect(1180, 120, 62, 34)), ("Start/Pause", pygame.Rect(1040, 176, 202, 36)),
        ("Reset", pygame.Rect(1040, 220, 202, 36)),
        ("Agents -", pygame.Rect(1040, 268, 97, 32)), ("Agents +", pygame.Rect(1145, 268, 97, 32)),
        ("Speed -", pygame.Rect(1040, 308, 97, 32)), ("Speed +", pygame.Rect(1145, 308, 97, 32)),
        ("Seed -", pygame.Rect(1040, 348, 97, 32)), ("Seed +", pygame.Rect(1145, 348, 97, 32)),
        ("Path", pygame.Rect(1040, 392, 62, 32)), ("Safety", pygame.Rect(1110, 392, 62, 32)),
        ("Risk", pygame.Rect(1180, 392, 62, 32)),
    ]
    frames = 0
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: running = False
                elif event.key == pygame.K_SPACE: paused = not paused
                elif event.key == pygame.K_r: simulation = create_simulation(simulation.algorithm_name, simulation.agent_count, seed, scenario)
                elif event.key == pygame.K_p: show_path = not show_path
                elif event.key == pygame.K_s: show_safety = not show_safety
                elif event.key == pygame.K_c: show_risk = not show_risk
                elif event.key == pygame.K_UP:
                    index = min(len(AGENT_COUNTS) - 1, AGENT_COUNTS.index(simulation.agent_count) + 1)
                    simulation = create_simulation(simulation.algorithm_name, AGENT_COUNTS[index], seed, scenario)
                elif event.key == pygame.K_DOWN:
                    index = max(0, AGENT_COUNTS.index(simulation.agent_count) - 1)
                    simulation = create_simulation(simulation.algorithm_name, AGENT_COUNTS[index], seed, scenario)
                elif event.key == pygame.K_LEFTBRACKET: speed_multiplier = max(0.25, speed_multiplier / 2)
                elif event.key == pygame.K_RIGHTBRACKET: speed_multiplier = min(8.0, speed_multiplier * 2)
                elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                    name = {pygame.K_1: "naive", pygame.K_2: "vo", pygame.K_3: "orca"}[event.key]
                    simulation = create_simulation(name, simulation.agent_count, seed, scenario)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for label, rect in buttons:
                    if not rect.collidepoint(event.pos):
                        continue
                    if label in {"naive", "vo", "orca"}:
                        simulation = create_simulation(label, simulation.agent_count, seed, scenario)
                    elif label == "Start/Pause": paused = not paused
                    elif label == "Reset": simulation = create_simulation(simulation.algorithm_name, simulation.agent_count, seed, scenario)
                    elif label in {"Agents -", "Agents +"}:
                        offset = -1 if label.endswith("-") else 1
                        index = min(len(AGENT_COUNTS) - 1, max(0, AGENT_COUNTS.index(simulation.agent_count) + offset))
                        simulation = create_simulation(simulation.algorithm_name, AGENT_COUNTS[index], seed, scenario)
                    elif label in {"Speed -", "Speed +"}:
                        speed_multiplier = max(0.25, speed_multiplier / 2) if label.endswith("-") else min(8.0, speed_multiplier * 2)
                    elif label in {"Seed -", "Seed +"}:
                        seed = max(0, seed + (-1 if label.endswith("-") else 1))
                        simulation = create_simulation(simulation.algorithm_name, simulation.agent_count, seed, scenario)
                    elif label == "Path": show_path = not show_path
                    elif label == "Safety": show_safety = not show_safety
                    elif label == "Risk": show_risk = not show_risk
        if not paused and not simulation.finished:
            for _ in range(max(1, int(speed_multiplier))):
                simulation.step()
        renderer.draw(simulation, paused, show_path, show_safety, show_risk, speed_multiplier, buttons)
        pygame.display.flip()
        clock.tick(60)
        frames += 1
        if headless_steps and frames >= headless_steps:
            running = False
    pygame.quit()
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--algorithm", choices=["naive", "vo", "orca"], default="orca")
    parser.add_argument("--agents", type=int, choices=AGENT_COUNTS, default=20)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--scenario", choices=["basic", "warehouse", "crossing", "multi_robot", "crowded"], default="warehouse")
    parser.add_argument("--headless-steps", type=int, default=0, help="Render N frames with SDL dummy driver and exit.")
    args = parser.parse_args()
    raise SystemExit(run_ui(args.algorithm, args.agents, args.seed, args.scenario, args.headless_steps))
