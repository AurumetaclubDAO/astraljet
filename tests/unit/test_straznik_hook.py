"""Kontrola decyzji strażnika operacji.

Hook żyje w .claude/hooks/, poza pakietem src/, więc ładujemy go po ścieżce.
Testy pilnują przede wszystkim obejść zgłoszonych w przeglądzie PR #1:
zagnieżdżony `git -C ... add .` nie dawał żadnej decyzji, a zagnieżdżony
`git push --force` kończył się ASK, choć AGENTS.md wymaga bezwarunkowej odmowy.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "straznik.py"


def _load():
    spec = importlib.util.spec_from_file_location("straznik_hook", HOOK)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


straznik = _load()


def decision(tool: str, tool_input: dict[str, object]) -> str | None:
    result = straznik.decide({"tool_name": tool, "tool_input": tool_input})
    return result[0] if result else None


def bash(command: str) -> str | None:
    return decision("Bash", {"command": command})


class ForcePushTest(unittest.TestCase):
    def test_nested_force_push_is_denied_not_merely_asked(self) -> None:
        self.assertEqual("deny", bash("bash -c 'git -C /tmp/repo push --force origin main'"))
        self.assertEqual("deny", bash('bash -c "git push -f origin main"'))
        self.assertEqual("deny", bash("bash -c 'git push --delete origin feature'"))

    def test_direct_force_push_stays_denied(self) -> None:
        self.assertEqual("deny", bash("git push --force"))
        self.assertEqual("deny", bash("git push --mirror"))

    def test_plain_push_still_asks(self) -> None:
        self.assertEqual("ask", bash("git push"))
        self.assertEqual("ask", bash("bash -c 'git push origin main'"))

    def test_dry_run_push_is_not_denied(self) -> None:
        self.assertEqual("ask", bash("git push --force --dry-run"))


class BroadAddTest(unittest.TestCase):
    def test_global_options_do_not_hide_a_broad_add(self) -> None:
        # -C i --git-dir to standardowe globalne opcje Git; skaner musi je pominąć
        # razem z wartościami, zanim rozpozna podkomendę.
        self.assertEqual("deny", bash("git -C /tmp/repo add ."))
        self.assertEqual("deny", bash("bash -c 'git -C /tmp/repo add .'"))
        self.assertEqual("deny", bash("git --git-dir=/tmp/x add --all"))
        self.assertEqual("deny", bash("git -c core.pager=cat add -A"))

    def test_direct_broad_add_stays_denied(self) -> None:
        self.assertEqual("deny", bash("git add -A"))
        self.assertEqual("deny", bash("git add ."))

    def test_specific_paths_are_allowed(self) -> None:
        self.assertIsNone(bash("git add src/astraljet/cli.py"))
        self.assertIsNone(bash("git add tests/unit/test_straznik_hook.py"))

    def test_commit_all_is_denied(self) -> None:
        self.assertEqual("deny", bash('git commit -a -m "x"'))


class SecretsTest(unittest.TestCase):
    def test_env_is_never_read(self) -> None:
        self.assertEqual("deny", decision("Read", {"file_path": "D:/Astra Jet/.env"}))
        self.assertEqual("deny", bash("cat .env"))

    def test_env_example_is_allowed(self) -> None:
        self.assertIsNone(decision("Read", {"file_path": "D:/Astra Jet/.env.example"}))


class ReadOnlyTest(unittest.TestCase):
    def test_reads_and_status_pass_without_a_decision(self) -> None:
        self.assertIsNone(bash("cat README.md"))
        self.assertIsNone(bash("git status --short"))

    def test_operational_surfaces_still_ask(self) -> None:
        self.assertEqual("ask", bash("python mt5_connector.py"))
        self.assertEqual("ask", bash("npm run deploy"))


if __name__ == "__main__":
    unittest.main()
