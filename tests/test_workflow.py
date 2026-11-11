"""The refresh workflow is kept intact and manual-only; re-enabling is one line (SPEC §11.5)."""
import re
import unittest

import yaml

from agesdk.db import PROJECT_ROOT

WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "weekly-refresh.yml"
SCHEDULE_LINE = '  # schedule: [{cron: "17 6 * * 1"}]'


class RefreshWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text()
        cls.wf = yaml.safe_load(cls.text)
        cls.triggers = cls.wf.get("on", cls.wf.get(True))     # PyYAML reads `on:` as True

    def test_manual_only(self):
        self.assertEqual(self.triggers, {"workflow_dispatch": {}})

    def test_reenabling_is_one_line(self):
        self.assertEqual(self.text.count(SCHEDULE_LINE), 1)
        enabled = yaml.safe_load(self.text.replace(SCHEDULE_LINE, SCHEDULE_LINE.replace("# ", "", 1)))
        on = enabled.get("on", enabled.get(True))
        self.assertEqual(on["schedule"], [{"cron": "17 6 * * 1"}])
        self.assertIn("workflow_dispatch", on)

    def test_pipeline_intact(self):
        steps = [s.get("name") for s in self.wf["jobs"]["refresh"]["steps"]]
        for name in ("Restore state", "Tests", "Refresh", "Commit changelog and open issue",
                     "Save state (new dated release)"):
            self.assertIn(name, steps)
        run = "\n".join(s.get("run", "") for s in self.wf["jobs"]["refresh"]["steps"])
        self.assertIn("python -m agesdk refresh", run)
        self.assertIn("state-backups prune", run)
        self.assertIn("state-backups latest", run)
        self.assertNotRegex(run, r"--clobber")                 # never overwrite a backup

    def test_changelog_only_on_transitions(self):
        step = next(s for s in self.wf["jobs"]["refresh"]["steps"]
                    if s.get("name") == "Commit changelog and open issue")
        self.assertEqual(step["if"], "steps.refresh.outputs.transitions != '0'")


if __name__ == "__main__":
    unittest.main()
