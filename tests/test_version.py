"""Version consistency tests — ensure single source of truth."""

import ast
from pathlib import Path

ROOT = Path(__file__).parent.parent


class TestVersionConsistency:
    """_version.py is the single source of truth for version."""

    def test_version_file_exists(self):
        vf = ROOT / "src" / "csda_toolkit" / "_version.py"
        assert vf.exists(), f"_version.py not found at {vf}"

    def test_version_file_parses(self):
        vf = ROOT / "src" / "csda_toolkit" / "_version.py"
        src = vf.read_text(encoding="utf-8")
        ast.parse(src)

    def test_version_format(self):
        vf = ROOT / "src" / "csda_toolkit" / "_version.py"
        src = vf.read_text(encoding="utf-8")
        tree = ast.parse(src)

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__version__":
                        assert isinstance(node.value, ast.Constant), (
                            "__version__ must be a string literal"
                        )
                        assert isinstance(node.value.value, str), (
                            "__version__ must be a string"
                        )
                        version = node.value.value
                        # PEP 440 format: major.minor.patch
                        parts = version.split(".")
                        assert len(parts) == 3, (
                            f"Version '{version}' should be major.minor.patch"
                        )
                        for p in parts:
                            assert p.isdigit(), (
                                f"Version segment '{p}' should be numeric"
                            )

    def test_init_imports_version(self):
        """__init__.py imports __version__ from _version."""
        init_file = ROOT / "src" / "csda_toolkit" / "__init__.py"
        src = init_file.read_text(encoding="utf-8")
        tree = ast.parse(src)

        found_import = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                # 'from ._version import __version__' → module='_version', level=1
                if node.module == "_version" and hasattr(node, "level"):
                    for alias in node.names:
                        if alias.name == "__version__":
                            found_import = True

        assert found_import, (
            "__init__.py should contain 'from ._version import __version__'"
        )

    def test_pyproject_toml_uses_dynamic_version(self):
        """pyproject.toml reads version dynamically from _version.__version__."""
        pyproject = ROOT / "pyproject.toml"
        src = pyproject.read_text(encoding="utf-8")
        assert 'dynamic = ["version"]' in src, (
            "pyproject.toml must have dynamic = ['version']"
        )
        assert 'attr = "csda_toolkit._version.__version__"' in src, (
            "pyproject.toml must use attr to read _version.__version__"
        )
