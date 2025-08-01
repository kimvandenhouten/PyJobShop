from ortools.sat.python.cp_model import (
    CpModel,
    LinearExpr,
    LinearExprT,
)

import pyjobshop.solvers.utils as utils
from pyjobshop.constants import MAX_VALUE
from pyjobshop.ProblemData import Machine, ProblemData
from pyjobshop.ProblemData import Objective as DataObjective

from .Variables import Variables


class Objective:
    """
    Builds the objective expressions of the OR-Tools model.
    """

    def __init__(
        self, model: CpModel, data: ProblemData, variables: Variables
    ):
        self._model = model
        self._data = data
        self._variables = variables

    def _makespan_expr(self) -> LinearExprT:
        """
        Returns an expression representing the makespan of the model.
        """
        if not self._variables.task_vars:
            return LinearExpr.constant(0)

        makespan = self._model.new_int_var(0, MAX_VALUE, "makespan")
        completion_times = [var.end for var in self._variables.task_vars]
        self._model.add_max_equality(makespan, completion_times)
        return makespan

    def _tardy_jobs_expr(self) -> LinearExprT:
        """
        Returns an expression representing the number of tardy jobs.
        """
        model, data = self._model, self._data
        is_tardy_vars = []

        for job, job_var in zip(data.jobs, self._variables.job_vars):
            assert job.due_date is not None
            is_tardy = model.new_bool_var(f"is_tardy_{job}")
            model.add(job_var.end > job.due_date).only_enforce_if(is_tardy)
            model.add(job_var.end <= job.due_date).only_enforce_if(~is_tardy)
            is_tardy_vars.append(is_tardy)

        weights = [job.weight for job in data.jobs]
        return LinearExpr.weighted_sum(is_tardy_vars, weights)

    def _total_flow_time_expr(self) -> LinearExprT:
        """
        Returns an expression representing the total flow time of jobs.
        """
        model, data = self._model, self._data
        flow_time_vars = []

        for job, var in zip(data.jobs, self._variables.job_vars):
            flow_time = model.new_int_var(0, MAX_VALUE, f"flow_time_{job}")
            model.add_max_equality(flow_time, [0, var.end - job.release_date])
            flow_time_vars.append(flow_time)

        weights = [job.weight for job in data.jobs]
        return LinearExpr.weighted_sum(flow_time_vars, weights)

    def _total_tardiness_expr(self) -> LinearExprT:
        """
        Returns an expression representing the total tardiness of jobs.
        """
        model, data = self._model, self._data
        tardiness_vars = []

        for job, var in zip(data.jobs, self._variables.job_vars):
            assert job.due_date is not None
            tardiness = model.new_int_var(0, MAX_VALUE, f"tardiness_{job}")
            model.add_max_equality(tardiness, [0, var.end - job.due_date])
            tardiness_vars.append(tardiness)

        weights = [job.weight for job in data.jobs]
        return LinearExpr.weighted_sum(tardiness_vars, weights)

    def _total_earliness_expr(self) -> LinearExprT:
        """
        Returns an expression representing the total earliness of jobs.
        """
        model, data = self._model, self._data
        earliness_vars = []

        for job, var in zip(data.jobs, self._variables.job_vars):
            assert job.due_date is not None
            earliness = model.new_int_var(0, MAX_VALUE, f"earliness_{job}")
            model.add_max_equality(earliness, [0, job.due_date - var.end])
            earliness_vars.append(earliness)

        weights = [job.weight for job in data.jobs]
        return LinearExpr.weighted_sum(earliness_vars, weights)

    def _max_tardiness_expr(self) -> LinearExprT:
        """
        Returns an expression representing the maximum tardiness of jobs.
        """
        model, data = self._model, self._data
        tardiness_vars = []

        for job, var in zip(data.jobs, self._variables.job_vars):
            assert job.due_date is not None
            tardiness = model.new_int_var(0, MAX_VALUE, f"tardiness_{job}")
            model.add_max_equality(tardiness, [0, var.end - job.due_date])
            tardiness_vars.append(job.weight * tardiness)

        max_tardiness = model.new_int_var(0, MAX_VALUE, "max_tardiness")
        model.add_max_equality(max_tardiness, tardiness_vars)
        return max_tardiness

    def _max_lateness_expr(self) -> LinearExprT:
        """
        Returns an expression representing the maximum tardiness of jobs.
        """
        model, data = self._model, self._data
        lateness_vars = []

        for job, var in zip(data.jobs, self._variables.job_vars):
            assert job.due_date is not None
            lateness = model.new_int_var(
                -MAX_VALUE, MAX_VALUE, f"lateness_{job}"
            )
            model.add(lateness == var.end - job.due_date)
            lateness_vars.append(job.weight * lateness)

        max_lateness = model.new_int_var(-MAX_VALUE, MAX_VALUE, "max_lateness")
        model.add_max_equality(max_lateness, lateness_vars)
        return max_lateness

    def _total_setup_time_expr(self) -> LinearExprT:
        """
        Returns an expression representing the total setup time of tasks.
        """
        data, variables = self._data, self._variables
        setup_times = utils.setup_times_matrix(data)

        setup_time_vars = []
        for res_idx, resource in enumerate(data.resources):
            if not isinstance(resource, Machine):
                continue

            seq_var = variables.sequence_vars[res_idx]
            if not seq_var.is_active:
                continue

            for task_idx1 in range(data.num_tasks):
                for task_idx2 in range(data.num_tasks):
                    var1 = variables.assign_vars.get((task_idx1, res_idx))
                    var2 = variables.assign_vars.get((task_idx2, res_idx))
                    if not (var1 and var2):
                        continue

                    setup = (
                        setup_times[res_idx, task_idx1, task_idx2]
                        if setup_times is not None
                        else 0
                    )
                    arc_selected = seq_var.arcs[task_idx1, task_idx2]
                    setup_time_vars.append(arc_selected * setup)

        return LinearExpr.sum(setup_time_vars)

    def _objective_expr(self, objective: DataObjective) -> LinearExprT:
        """
        Returns the expression corresponding to the given objective.
        """
        items = [
            (objective.weight_makespan, self._makespan_expr),
            (objective.weight_tardy_jobs, self._tardy_jobs_expr),
            (objective.weight_total_tardiness, self._total_tardiness_expr),
            (objective.weight_total_flow_time, self._total_flow_time_expr),
            (objective.weight_total_earliness, self._total_earliness_expr),
            (objective.weight_max_tardiness, self._max_tardiness_expr),
            (objective.weight_max_lateness, self._max_lateness_expr),
            (objective.weight_total_setup_time, self._total_setup_time_expr),
        ]
        exprs = [weight * expr() for weight, expr in items if weight > 0]
        return LinearExpr.sum(exprs)

    def add_objective(self):
        """
        Adds the objective expression to the CP model.
        """
        obj_expr = self._objective_expr(self._data.objective)
        self._model.minimize(obj_expr)
