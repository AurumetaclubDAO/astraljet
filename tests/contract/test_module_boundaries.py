from __future__ import annotations

import ast
import unittest
from pathlib import Path


class ModuleBoundaryContractTest(unittest.TestCase):
    def test_lab_never_imports_executor(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        violations: list[str] = []
        for path in sorted((project_root / "src" / "astraljet" / "lab").glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("astraljet.executor"):
                            violations.append(f"{path.name}:{node.lineno}:{alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    if module.startswith("astraljet.executor") or (
                        node.level and module.startswith("executor")
                    ):
                        violations.append(f"{path.name}:{node.lineno}:{module}")
        self.assertEqual([], violations, "Warstwa ASTRA Pro/lab importuje Wykonawcę")


if __name__ == "__main__":
    unittest.main()
