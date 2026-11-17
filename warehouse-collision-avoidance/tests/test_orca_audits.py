import json
import numpy as np
import pytest
from algorithms import create_algorithm
from simulator.agents import Agent,ControlledRobot
from newton_safety import orca_audit


def test_orca_audit_distinguishes_tracking_and_infeasibility():
    class Solver:
        # Feasible velocities have v_x >= 1.
        last_lines=[(np.array([1.,0.]),np.array([0.,-1.]))]
        infeasible=False
    result=orca_audit(Solver(),[0,0],[0,0],np.array([1.,0.]),np.array([0.,0.]),[],0,0.,[],[])
    assert result["max_target_constraint_residual"]==0
    assert result["max_actual_constraint_residual"]==1
    assert result["hypothesis"]=="physical_tracking_error"
    Solver.infeasible=True
    assert orca_audit(Solver(),[0,0],[0,0],[0,0],[0,0],[],0,0.,[],[])["hypothesis"]=="infeasible_constraints"
    json.dumps(result,allow_nan=False)


def test_actual_orca_halfplane_residual_is_feasible_when_solution_exists():
    robot=ControlledRobot("r",np.array([0.,0.]),np.zeros(2),np.array([10.,0.]))
    agent=Agent("w",np.array([2.,0.]),np.array([-.5,0.]),np.array([-10.,0.]))
    algorithm=create_algorithm("orca")
    velocity,_=algorithm.choose_velocity(robot,[agent],np.array([1.,0.]),.35,1/30)
    audit=orca_audit(algorithm,[0,0],[0,0],velocity,velocity,[],0,0.,[],[])
    assert audit["max_target_constraint_residual"] <= 1e-9
    assert not algorithm.infeasible
