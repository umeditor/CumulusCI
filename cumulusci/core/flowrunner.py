""" FlowRunner contains the logic for actually running a flow.

Flows are an integral part of CCI, they actually *do the thing*. We've been getting
along quite nicely with BaseFlow, which turns a flow definition into a callable
object that runs the flow in one fell swoop. We named it BaseFlow thinking that,
like tasks, specific flows might subclass it to extend behavior. In practice,
unlike BaseTask, subclasses ended up representing variations in how the flow
should actually be executed. We added callback hooks like pre_task and post_task
for host systems embedding cci, like web apps, to inspect the flow in progress.

BaseFlow suited us well.

FlowRunner is a v2 API for flows in CCI. The object of interest is the `FlowRunner`
instead of the flow being run.

Upon initialization, FlowRunner:
- Creates a logger
- Validates that there are no cycles in the given flow_config
- Validates that the flow_config is using new-style-steps
- Collects a list of StepSpec objects that define what the flow will do.

Upon running the flow, FlowRunner:
- Refreshes the org credentials
- Runs each StepSpec in order
- * Logs the task or skip
- * Updates any ^^ task option values with return_values references
- * handles any exceptions and sets return values

Option values/overrides can be passed in at a number of levels, in increasing order of priority:
- Task default (i.e. `.tasks.TASKNAME.options`)
- Flow definition task options (i.e. `.flows.FLOWNAME.steps.STEPNUM.options`)
- Flow definition subflow options (i.e. `.flows.FLOWNAME.steps.STEPNUM.options.TASKNAME`)
    see `dev_org_namespaced` for an example
- Flow runtime (i.e. on the commandline)

"""

# we don't actually use this set of imports, they're just in type
# comments, which require explicit runtime import when checking...
try:
    from typing import List
except ImportError:
    pass

import copy
import logging
from distutils.version import LooseVersion

from cumulusci.core.exceptions import FlowConfigError, FlowInfiniteLoopError


class StepSpec(object):
    """ simple namespace to describe what the flowrunner should do each step """

    def __init__(self, step_num, task_name, task_options, allow_failure=False):
        self.step_num = step_num
        self.task_name = task_name
        self.task_options = task_options
        self.allow_failure = allow_failure

    def __repr__(self):
        return "<StepSpec {num}:{name} {cfg}>".format(
            num=self.step_num, name=self.task_name, cfg=self.task_options
        )


class NoOpStep(object):
    """ Sentinel object used to indicate a no-op step. """

    def __repr__(self):
        return "NoOpStep"

    def __str__(self):
        return self.__repr__()


class FlowRunner(object):
    def __init__(
        self, project_config, flow_config, org_config, options=None, skip=None
    ):
        self.project_config = project_config
        self.flow_config = flow_config
        self.org_config = org_config

        if not options:
            options = {}
        self.options = options

        if not skip:
            skip = []
        self.skip = skip

        self.logger = self._init_logger()
        self.steps = self._init_steps()  # type: List[StepSpec]

    def _init_logger(self):
        """
        Returns a logger-like object to use for the duration of the flow.

        This could be a static in the base implementation, but subclasses may want to
        use instance details to log to the right place in the database.

        :return: logging.Logger
        """
        return logging.getLogger(__name__)

    def _init_steps(self):
        """
        Given the flow config and everything else, create a list of steps to run.

        :return: List[StepSpec]
        """
        config_steps = self.flow_config.steps

        self._check_old_yaml_format()
        self._check_infinite_flows(config_steps)

        steps = []

        for number, step_config in config_steps.items():
            specs = self._visit_step(number, step_config)
            steps.extend(specs)

        return steps

    def _visit_step(self, number, step_config, visited_steps=None, parent_options=None):
        number = LooseVersion(str(number))

        if visited_steps is None:
            visited_steps = []

        if parent_options is None:
            parent_options = {}

        # Step Validation
        # - A step is either a task OR a flow.
        if all(k in step_config for k in ("flow", "task")):
            raise FlowConfigError(
                "Step {} is configured as both a flow AND a task. \n\t{}.".format(
                    number, step_config
                )
            )

        # Skips
        # - either in YAML (with the None string)
        # - or by providing a skip list to the FlowRunner at initialization.
        if (
            ("flow" in step_config and step_config["flow"] == "None")
            or ("task" in step_config and step_config["task"] == "None")
            or ("task" in step_config and step_config["task"] in self.skip)
        ):
            visited_steps.append(
                StepSpec(number, NoOpStep(), step_config.get("options", {}))
            )
            return visited_steps

        if "task" in step_config:
            name = step_config["task"]

            step_options = copy.deepcopy(parent_options.get(name, {}))
            step_options.update(step_config.get("options", {}))

            visited_steps.append(
                StepSpec(
                    number, name, step_options, step_config.get("ignore_failure", False)
                )
            )
            return visited_steps

        if "flow" in step_config:
            name = step_config["flow"]
            step_options = step_config.get("options", {})
            flow_config = self.project_config.get_flow(name)
            for sub_number, sub_stepconf in flow_config.steps.items():
                # append the flow number to the child number, since its a LooseVersion.
                num = "{}.{}".format(number, sub_number)
                self._visit_step(
                    num, sub_stepconf, visited_steps, parent_options=step_options
                )

        return visited_steps

    def _check_old_yaml_format(self):
        # copied from BaseFlow
        if self.flow_config.steps is None:
            if self.flow_config.tasks:
                raise FlowConfigError(
                    'Old flow syntax detected.  Please change from "tasks" to "steps" in the flow definition.'
                )
            else:
                raise FlowConfigError("No steps found in the flow definition")

    def _check_infinite_flows(self, steps, flows=None):
        """
        Recursively loop through the flow_config and check if there are any cycles.

        :param steps: Set of step definitions to loop through
        :param flows: Flows already visited.
        :return: None
        """
        # copied from BaseFlow
        if flows is None:
            flows = []
        for step in steps.values():
            if "flow" in step:
                flow = step["flow"]
                if flow == "None":
                    continue
                if flow in flows:
                    raise FlowInfiniteLoopError(
                        "Infinite flows detected with flow {}".format(flow)
                    )
                flows.append(flow)
                flow_config = self.project_config.get_flow(flow)
                self._check_infinite_flows(flow_config.steps, flows)
