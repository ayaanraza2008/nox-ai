"""Regression tests for the bounded multi-agent swarm."""
import asyncio
import json
import os
import tempfile
import unittest

from backend.agent_swarm import SwarmError, SwarmManager


class FakeProvider:
    def __init__(self, planner=None):
        self.planner = planner or {"tasks": [
            {"id": "a1", "role": "architect", "title": "Define plan", "instruction": "Define module boundaries.", "depends_on": []},
            {"id": "a2", "role": "security", "title": "Review risks", "instruction": "Identify safety risks.", "depends_on": []},
            {"id": "a3", "role": "qa", "title": "Validate plan", "instruction": "Use the plan and security review.", "depends_on": ["a1", "a2"]},
        ]}
        self.calls = []

    async def __call__(self, messages, timeout=90):
        self.calls.append(messages)
        if "task planner" in messages[0]["content"].lower():
            return json.dumps(self.planner)
        if "integration and qa lead" in messages[0]["content"].lower():
            return "Unified deliverable with limitations."
        await asyncio.sleep(0.01)
        return "Specialist artifact."


class SwarmTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_db = os.environ.get("NOX_SWARM_DB")
        os.environ["NOX_SWARM_DB"] = os.path.join(self.temp.name, "swarm.sqlite3")
        self.provider = FakeProvider()
        self.manager = SwarmManager(provider=self.provider)

    async def asyncTearDown(self):
        runners = list(self.manager.runners.values())
        for runner in runners:
            if not runner.done():
                runner.cancel()
        if runners:
            await asyncio.gather(*runners, return_exceptions=True)
        if self.old_db is None:
            os.environ.pop("NOX_SWARM_DB", None)
        else:
            os.environ["NOX_SWARM_DB"] = self.old_db
        self.temp.cleanup()

    async def _wait(self, job_id):
        for _ in range(200):
            job = self.manager.get(job_id, "owner-a")
            if job["status"] in ("completed", "failed", "cancelled"):
                return job
            await asyncio.sleep(0.01)
        self.fail("Swarm job did not reach a terminal state in time.")

    async def test_parallel_specialists_follow_dependencies_and_integrate(self):
        created = await self.manager.create("Plan a secure login and dashboard feature", "en", "owner-a")
        final = await self._wait(created["id"])
        self.assertEqual(final["status"], "completed", final["error"])
        self.assertEqual(len(final["agents"]), 3)
        self.assertTrue(all(a["status"] == "completed" for a in final["agents"]))
        self.assertEqual(final["result"], "Unified deliverable with limitations.")
        qa_call = next(m for m in self.provider.calls if "Testing and QA Agent" in m[0]["content"])
        self.assertIn("dependency_artifacts", qa_call[1]["content"])
        self.assertIn("Specialist artifact.", qa_call[1]["content"])

    async def test_invalid_circular_plan_is_rejected_before_agent_execution(self):
        self.provider.planner = {"tasks": [
            {"id": "a1", "role": "architect", "title": "A", "instruction": "Do A", "depends_on": ["a2"]},
            {"id": "a2", "role": "qa", "title": "B", "instruction": "Do B", "depends_on": ["a1"]},
        ]}
        created = await self.manager.create("Plan a multi-step feature carefully", "en", "owner-a")
        final = await self._wait(created["id"])
        self.assertEqual(final["status"], "failed")
        self.assertIn("circular dependency", final["error"])
        self.assertEqual(final["agents"], [])

    async def test_job_results_are_scoped_to_browser_owner(self):
        created = await self.manager.create("Plan a secure login and dashboard feature", "en", "owner-a")
        self.assertIsNone(self.manager.get(created["id"], "owner-b"))
        self.assertEqual(self.manager.list("owner-b"), [])

    async def test_provider_missing_key_fails_truthfully(self):
        manager = SwarmManager(provider=None)
        async def no_key(messages, timeout=90):
            raise SwarmError("No AI provider is configured. Set OPENROUTER_API_KEY on the server.")
        manager.provider = no_key
        job = await manager.create("Plan a secure login and dashboard feature", "en", "owner-a")
        final = await self._wait(job["id"])
        self.assertEqual(final["status"], "failed")
        self.assertIn("OPENROUTER_API_KEY", final["error"])


if __name__ == "__main__":
    unittest.main()
