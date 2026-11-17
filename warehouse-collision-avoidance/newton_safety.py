"""Safety metrics and ORCA audits. Executed outside the avoidance timing region."""
from __future__ import annotations
import math
import numpy as np
from simulator.physics import swept_minimum_separation


def rectangle_distance(position, rect):
    p=np.asarray(position,dtype=float)
    if isinstance(rect,dict):
        angle=np.deg2rad(rect["rotation"]);d=p-np.asarray(rect["position"])
        p=np.array([np.cos(angle)*d[0]+np.sin(angle)*d[1],-np.sin(angle)*d[0]+np.cos(angle)*d[1]])
        w,h=rect["size"];rect=(-w/2,-h/2,w,h)
    x,y,w,h=rect
    q=np.abs(p-np.array([x+w/2,y+h/2]))-np.array([w/2,h/2])
    return float(np.linalg.norm(np.maximum(q,0))+min(float(max(q)),0))


def clearances(robot, agents, width, height, obstacles):
    dynamic=min((float(np.linalg.norm(robot.position-a.position))-robot.radius-a.radius for a in agents),default=math.inf)
    static=min([robot.position[0],width-robot.position[0],robot.position[1],height-robot.position[1]]
               +[rectangle_distance(robot.position,r) for r in obstacles])-robot.radius
    return dynamic,float(static)


def orca_audit(algorithm, before, after, target, velocity, neighbors, frame, t, collisions, safety):
    lines=getattr(algorithm,"last_lines",[])
    def residual(v):
        return max([0.]+[float(d[0]*(p-v)[1]-d[1]*(p-v)[0]) for p,d in lines])
    tr,ar=residual(np.asarray(target)),residual(np.asarray(velocity))
    infeasible=bool(getattr(algorithm,"infeasible",False))
    return {"frame":frame,"t":t,"robot_before":before,"robot_after":after,
            "target_velocity":list(map(float,target)),"actual_velocity":list(map(float,velocity)),
            "tracking_error_mps":float(np.linalg.norm(np.asarray(target)-velocity)),
            "max_target_constraint_residual":tr,"max_actual_constraint_residual":ar,"tolerance":1e-9,
            "infeasible_fallback":infeasible,"collisions":collisions,"safety_neighbors":safety,
            "hypothesis":("infeasible_constraints" if infeasible else
                          "physical_tracking_error" if ar>1e-9 and tr<=1e-9 else
                          "target_constraint_violation" if tr>1e-9 else "prediction_or_noncooperative_motion"),
            "neighbors":neighbors,"responsibility":"R0 100%; scripted agents are noncooperative",
            "halfplanes":[{"point":p.tolist(),"direction":d.tolist()} for p,d in lines]}
