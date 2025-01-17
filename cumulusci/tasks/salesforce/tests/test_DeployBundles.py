from unittest import mock
import os
import unittest

from cumulusci.core.flowrunner import StepSpec
from cumulusci.tasks.salesforce import DeployBundles
from cumulusci.utils import temporary_dir
from .util import create_task


class TestDeployBundles(unittest.TestCase):
    def test_run_task(self):
        with temporary_dir() as path:
            os.mkdir("src")
            with open(os.path.join(path, "file"), "w"):
                pass
            task = create_task(DeployBundles, {"path": path})
            task._get_api = mock.Mock()
            task()
            task._get_api.assert_called_once()

    def test_run_task__path_not_found(self):
        with temporary_dir() as path:
            pass
        task = create_task(DeployBundles, {"path": path})
        task._get_api = mock.Mock()
        task()
        task._get_api.assert_not_called()

    def test_freeze(self):
        with temporary_dir() as path:
            os.mkdir(".git")
            os.makedirs("unpackaged/test")
            task = create_task(DeployBundles, {"path": path + "/unpackaged"})
            step = StepSpec(1, "deploy_bundles", task.task_config, None)
            steps = task.freeze(step)
            self.assertEqual(
                [
                    {
                        "is_required": True,
                        "kind": "metadata",
                        "name": "Deploy unpackaged/test",
                        "path": "deploy_bundles.test",
                        "step_num": "1.1",
                        "task_class": "cumulusci.tasks.salesforce.UpdateDependencies",
                        "task_config": {
                            "options": {
                                "dependencies": [
                                    {
                                        "ref": task.project_config.repo_commit,
                                        "repo_name": "TestRepo",
                                        "repo_owner": "TestOwner",
                                        "subfolder": "unpackaged/test",
                                    }
                                ]
                            },
                            "checks": [],
                        },
                    }
                ],
                steps,
            )

    def test_freeze__bad_path(self):
        task = create_task(DeployBundles, {"path": "/bogus"})
        step = StepSpec(1, "deploy_bundles", task.task_config, None)
        steps = task.freeze(step)
        self.assertEqual([], steps)
