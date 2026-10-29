import os
import subprocess
import sys

import pytest


@pytest.mark.parametrize("explicit_ui", [False, True])
def test_ui_dependency_is_only_required_for_execution(explicit_ui):
    script = """
import importlib.abc
import sys
import pytest

class BlockPlaywright(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'playwright' or fullname.startswith('playwright.'):
            raise ModuleNotFoundError('Playwright deliberately unavailable')

sys.meta_path.insert(0, BlockPlaywright())
arguments = ['-q', '-p', 'no:cacheprovider', '--confcutdir=tests/ui']
explicit_ui = sys.argv[1] == 'True'
if explicit_ui:
    arguments += ['-x', '-m', 'ui', 'tests/ui/test_cms_workflows.py::test_local_report_error']
else:
    arguments += ['--collect-only', 'tests/ui']
code = pytest.main(arguments)
if explicit_ui:
    assert code == pytest.ExitCode.TESTS_FAILED, code
else:
    assert code == pytest.ExitCode.NO_TESTS_COLLECTED, code
    assert not any(name.startswith('playwright') for name in sys.modules)
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", script, str(explicit_ui)],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    if explicit_ui:
        assert "Playwright deliberately unavailable" in result.stdout