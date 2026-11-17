from .naive import NaiveAvoidance
from .orca import ORCAAvoidance
from .velocity_obstacle import VelocityObstacleAvoidance


def create_algorithm(name: str):
    algorithms = {
        "naive": NaiveAvoidance,
        "vo": VelocityObstacleAvoidance,
        "orca": ORCAAvoidance,
    }
    try:
        return algorithms[name.lower()]()
    except KeyError as error:
        raise ValueError(f"지원하지 않는 알고리즘: {name}") from error


__all__ = ["create_algorithm", "NaiveAvoidance", "VelocityObstacleAvoidance", "ORCAAvoidance"]
