#!/usr/bin/env python3
"""scripts/ 下各脚本的端到端测试：子进程跑真实脚本，夹具用临时目录，结束自动清理。
只读仓库文件，所有写入都发生在系统临时目录。"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# 仓库根目录与脚本目录（本文件位于 scripts/tests/）
ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"


def run_script(name: str, *args) -> subprocess.CompletedProcess:
    """以子进程方式运行 scripts/<name>，强制子进程 stdout 用 utf-8 且不产生 __pycache__。"""
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run(
        [sys.executable, str(SCRIPTS / name), *[str(a) for a in args]],
        capture_output=True, text=True, encoding="utf-8", env=env,
    )


def assert_ok(case: unittest.TestCase, proc: subprocess.CompletedProcess) -> None:
    """断言子进程 exit 0，失败时附带 stderr 便于定位。"""
    case.assertEqual(proc.returncode, 0, msg=f"stderr: {proc.stderr}")


def write_json(path: Path, data) -> None:
    """写 JSON 夹具文件。"""
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


class InventoryTest(unittest.TestCase):
    """inventory：跳过目录、语言分类、lines 字段口径。"""

    def test_skip_dirs_by_lang_and_lines(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            (target / "app.py").write_text("print(1)\nprint(2)\n", encoding="utf-8")
            (target / "src").mkdir()
            (target / "src" / "util.js").write_text("const a = 1;\n", encoding="utf-8")
            (target / "src" / "typ.ts").write_text("const b: number = 2;\n", encoding="utf-8")
            (target / "README.md").write_text("# readme\n", encoding="utf-8")
            (target / ".git").mkdir()
            (target / ".git" / "config").write_text("[core]\n", encoding="utf-8")
            (target / "node_modules" / "pkg").mkdir(parents=True)
            (target / "node_modules" / "pkg" / "index.js").write_text("module.exports = 1;\n", encoding="utf-8")

            proc = run_script("inventory.py", target)
            assert_ok(self, proc)
            data = json.loads(proc.stdout)

            # .git 与 node_modules 整个跳过
            self.assertFalse(any(f.startswith((".git", "node_modules")) for f in data["files"]))
            self.assertIn(".git", data["skipped_dirs"])
            self.assertIn("node_modules", data["skipped_dirs"])
            # py/js/ts 分类（node_modules 里的 js 不计）
            self.assertEqual(data["by_lang"], {"py": 1, "js": 1, "ts": 1})
            # lines 只含源码文件，非源码 README.md 不在其中
            self.assertEqual(set(data["lines"]), {"app.py", "src/util.js", "src/typ.ts"})
            self.assertEqual(data["lines"]["app.py"], 2)


class TodoScanTest(unittest.TestCase):
    """todo_scan：命中 TODO/FIXME，README 开头与 docs/ 路径跳过。"""

    def test_hits_and_skips(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            (target / "a.py").write_text("# TODO: 修复这个\n# FIXME 立即处理\nprint(1)\n", encoding="utf-8")
            (target / "README_notes.py").write_text("# TODO: 不应命中\n", encoding="utf-8")
            (target / "docs").mkdir()
            (target / "docs" / "guide.py").write_text("# TODO: 也不应命中\n", encoding="utf-8")
            inv = target / "inv.json"
            write_json(inv, {"files": ["a.py", "README_notes.py", "docs/guide.py"]})

            proc = run_script("todo_scan.py", target, "--inventory", inv)
            assert_ok(self, proc)
            issues = json.loads(proc.stdout)

            self.assertEqual(len(issues), 2)
            self.assertEqual({i["tag"] for i in issues}, {"TODO", "FIXME"})
            self.assertTrue(all(i["file"] == "a.py" for i in issues))


class ComplexityTest(unittest.TestCase):
    """complexity：Python 长函数 medium、>30 分支 high、JS 箭头函数、压缩文件进 warnings。"""

    def test_thresholds_and_js(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            # 90 行 Python 函数（>80 且 <=160 -> medium）
            long_body = "\n".join("    x = 1" for _ in range(89))
            (target / "long.py").write_text(f"def long_function():\n{long_body}\n", encoding="utf-8")
            # 31 个 if 的 Python 函数（>30 -> high）
            branchy_body = "\n".join("    if a:\n        pass" for _ in range(31))
            (target / "branchy.py").write_text(f"def branchy_py(a):\n{branchy_body}\n", encoding="utf-8")
            # JS 箭头函数 16 个 if（>15 且 <=30 -> medium）
            ifs = "\n".join("  if (a) { b += 1; }" for _ in range(16))
            (target / "arrow.js").write_text(f"const branchyJs = (a) => {{\n  let b = 0;\n{ifs}\n}};\n", encoding="utf-8")
            # 单行超 1000 字符的压缩文件 -> 进 warnings
            (target / "min.js").write_text('var x = "' + "a" * 1100 + '";\n', encoding="utf-8")
            inv = target / "inv.json"
            write_json(inv, {"files": ["long.py", "branchy.py", "arrow.js", "min.js"]})

            proc = run_script("complexity.py", target, "--inventory", inv)
            assert_ok(self, proc)
            data = json.loads(proc.stdout)

            by_func = {i["function"]: i for i in data["issues"]}
            self.assertEqual(by_func["long_function"]["severity"], "medium")
            self.assertEqual(by_func["long_function"]["lines"], 90)
            self.assertEqual(by_func["branchy_py"]["severity"], "high")
            self.assertEqual(by_func["branchy_py"]["branches"], 31)
            self.assertEqual(by_func["branchyJs"]["severity"], "medium")
            self.assertEqual(by_func["branchyJs"]["file"], "arrow.js")
            self.assertEqual(len(data["warnings"]), 1)
            self.assertEqual(data["warnings"][0]["file"], "min.js")


class TestMapTest(unittest.TestCase):
    """test_map：missing 名单与 missing_ratio。"""

    def test_missing_and_ratio(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            inv = target / "inv.json"
            write_json(inv, {"files": ["src/app.py", "src/core.py", "tests/test_app.py"]})

            proc = run_script("test_map.py", target, "--inventory", inv)
            assert_ok(self, proc)
            data = json.loads(proc.stdout)

            self.assertEqual(data["checked"], 2)
            self.assertEqual(data["missing"], ["src/core.py"])
            self.assertEqual(data["missing_count"], 1)
            self.assertEqual(data["missing_ratio"], 0.5)


class DepsCheckTest(unittest.TestCase):
    """deps_check --offline：exit 0 且输出固定 skipped。"""

    def test_offline_fixed_output(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            inv = target / "inv.json"
            write_json(inv, {"files": []})

            proc = run_script("deps_check.py", target, "--inventory", inv, "--offline")
            assert_ok(self, proc)
            data = json.loads(proc.stdout)

            self.assertEqual(data["issues"], [])
            self.assertEqual(data["warnings"], [])
            self.assertEqual(data["skipped"], [
                {"rule": "deps", "reason": "离线模式：未发起网络请求，依赖检查跳过"}])


def make_result(**overrides) -> dict:
    """构造最小合法 result.json 夹具。"""
    result = {
        "project": "demo",
        "scanned_at": "2026-10-17T00:00:00Z",
        "target": "x",
        "inventory": {"files": 3, "source_files": 2},
        "issues": [],
        "skipped_rules": [],
        "score": 0,
        "grade": "F",
    }
    result.update(overrides)
    return result


class ScoreTest(unittest.TestCase):
    """score：小项目口径不变、N=100 折算、未知 rule 忽略。"""

    def run_score(self, result: dict, td: str) -> dict:
        path = Path(td) / "result.json"
        write_json(path, result)
        proc = run_script("score.py", path)
        assert_ok(self, proc)
        return json.loads(proc.stdout)

    def test_small_project_exact_score(self):
        with tempfile.TemporaryDirectory() as td:
            # N=10，1 条 high complexity：扣 5，complexity 得 20，总分 95 -> A
            result = make_result(
                inventory={"files": 12, "source_files": 10},
                issues=[{"rule": "complexity", "severity": "high", "file": "a.py", "line": 1, "message": "m"}])
            data = self.run_score(result, td)
            self.assertEqual(data["score"], 95)
            self.assertEqual(data["grade"], "A")

    def test_scale_factor_half(self):
        with tempfile.TemporaryDirectory() as td:
            # N=100，4 条 medium todo：factor=0.5，扣 4*3*0.5=6，todo 得 9，总分 94 -> A
            result = make_result(
                inventory={"files": 120, "source_files": 100},
                issues=[{"rule": "todo", "severity": "medium", "file": f"f{i}.py", "line": 1, "message": "m"}
                        for i in range(4)])
            data = self.run_score(result, td)
            self.assertEqual(data["score"], 94)
            self.assertEqual(data["grade"], "A")

    def test_unknown_rule_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            result = make_result(
                issues=[{"rule": "unknown_rule", "severity": "high", "file": "a.py", "line": 1, "message": "m"}])
            data = self.run_score(result, td)
            self.assertEqual(data["score"], 100)
            self.assertEqual(data["grade"], "A")


class RenderReportTest(unittest.TestCase):
    """render_report：jinja2 与 --no-jinja2 两条路径 exit 0 且含修复提示词小节。"""

    def render(self, td: str, *extra) -> str:
        result_path = Path(td) / "result.json"
        write_json(result_path, make_result(
            issues=[{"rule": "todo", "severity": "low", "file": "a.py", "line": 1,
                     "message": "遗留标记", "suggestion": None}]))
        out_path = Path(td) / "report.md"
        proc = run_script("render_report.py", result_path, "--out", out_path, *extra)
        assert_ok(self, proc)
        return out_path.read_text(encoding="utf-8")

    def test_jinja2_path(self):
        with tempfile.TemporaryDirectory() as td:
            text = self.render(td)
            self.assertIn("## 修复提示词", text)
            self.assertIn("```text", text)
            self.assertIn("遗留标记", text)

    def test_builtin_path(self):
        with tempfile.TemporaryDirectory() as td:
            text = self.render(td, "--no-jinja2")
            self.assertIn("## 修复提示词", text)
            self.assertIn("```text", text)
            self.assertIn("遗留标记", text)


if __name__ == "__main__":
    unittest.main()
