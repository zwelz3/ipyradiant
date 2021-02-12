""" important project paths

    this should not import anything not in py36+ stdlib, or any local paths
"""

# Copyright (c) 2021 ipyradiant contributors.
# Distributed under the terms of the Modified BSD License.

import json
import os
import platform
import re
from pathlib import Path

# platform
PLATFORM = os.environ.get("FAKE_PLATFORM", platform.system())
WIN = PLATFORM == "Windows"
OSX = PLATFORM == "Darwin"
UNIX = not WIN

# CI jank
SKIP_CONDA_PREFLIGHT = bool(json.loads(os.environ.get("SKIP_CONDA_PREFLIGHT", "false")))
# one of: None, wheel or sdist
INSTALL_ARTIFACT = os.environ.get("INSTALL_ARTIFACT")

# find root
SCRIPTS = Path(__file__).parent.resolve()
ROOT = SCRIPTS.parent

# top-level stuff
SETUP_PY = ROOT / "setup.py"
SETUP_CFG = ROOT / "setup.cfg"
NODE_MODULES = ROOT / "node_modules"
PACKAGE = ROOT / "package.json"
YARN_INTEGRITY = NODE_MODULES / ".yarn-integrity"
YARN_LOCK = ROOT / "yarn.lock"
CI = ROOT / ".github"
DODO = ROOT / "dodo.py"
BUILD = ROOT / "build"
DIST = ROOT / "dist"
ENVS = ROOT / "envs"
PROJ = ROOT / "anaconda-project.yml"
PROJ_LOCK = ROOT / "anaconda-project-lock.yml"
VENDOR = ROOT / "vendor"
CHANGELOG = ROOT / "CHANGELOG.md"
CONDARC = CI / ".condarc"

# tools
PY = ["python"]
PYM = [*PY, "-m"]
PIP = [*PYM, "pip"]
PREFLIGHT = [*PYM, "_scripts.preflight"]


JLPM = ["jlpm"]
JLPM_INSTALL = [*JLPM, "--ignore-optional", "--prefer-offline"]
LAB_EXT = ["jupyter", "labextension"]
CONDA_BUILD = ["conda-build"]
LAB = ["jupyter", "lab"]
AP = ["anaconda-project"]
AP_PREP = [*AP, "prepare", "--env-spec"]
APR = [*AP, "run", "--env-spec"]
APR_DEV = [*APR, "dev"]
APR_BUILD = [*APR, "build"]
APR_QA = [*APR, "qa"]

# env stuff
OK_ENV = {env: BUILD / f"prep_{env}.ok" for env in ["build", "qa", "dev"]}
FORCE_SERIAL_ENV_PREP = bool(
    json.loads(os.environ.get("FORCE_SERIAL_ENV_PREP", "true"))
)

# python stuff
PY_SRC = ROOT / "src" / "ipyradiant"
VERSION_PY = PY_SRC / "_version.py"

# lab stuff
LAB_APP_DIR = ENVS / "dev/share/jupyter/lab"
LAB_STAGING = LAB_APP_DIR / "staging"
LAB_LOCK = LAB_STAGING / "yarn.lock"
LAB_STATIC = LAB_APP_DIR / "static"
LAB_INDEX = LAB_STATIC / "index.html"


def _not_checkpoint(paths):
    """filter out paths that are in .ipynb_checkpoints"""
    return sorted(
        [p for p in paths if not p.is_dir() and ".ipynb_checkpoints" not in str(p)]
    )


# tests
EXAMPLES = ROOT / "examples"
EXAMPLE_DATA = EXAMPLES / "data"
EXAMPLE_DATASETS = [
    p for p in _not_checkpoint(EXAMPLE_DATA.glob("*")) if not p.name.endswith("*.md")
]
EXAMPLE_IPYNB = _not_checkpoint(EXAMPLES.rglob("*.ipynb"))
EXAMPLE_PY = [*EXAMPLES.rglob("*.py")]
PY_TESTS = PY_SRC / "tests"
BUILD_NBHTML = BUILD / "nbsmoke"

# mostly linting
ALL_PY_SRC = [*PY_SRC.rglob("*.py")]
ALL_PY = [DODO, *ALL_PY_SRC, *EXAMPLE_PY, *SCRIPTS.rglob("*.py")]
ALL_YML = [*ROOT.glob("*.yml"), *CI.rglob("*.yml")]
ALL_JSON = [*ROOT.glob("*.json")]
ALL_MD = [*ROOT.glob("*.md"), *EXAMPLE_DATA.glob("*.md")]
ALL_PRETTIER = [*ALL_YML, *ALL_JSON, *ALL_MD]

# conda
DIST_CONDA = DIST / "conda-bld"

# built files
OK_RELEASE = BUILD / "release.ok"
OK_PREFLIGHT_CONDA = BUILD / "preflight.conda.ok"
OK_PREFLIGHT_KERNEL = BUILD / "preflight.kernel.ok"
OK_PREFLIGHT_LAB = BUILD / "preflight.lab.ok"
OK_PREFLIGHT_RELEASE = BUILD / "preflight.release.ok"
HTML_COV_INDEX = BUILD / "htmlcov/index.html"
OK_BLACK = BUILD / "black.ok"
OK_FLAKE8 = BUILD / "flake8.ok"
OK_LINT = BUILD / "lint.ok"
OK_PYFLAKES = BUILD / "pyflakes.ok"
OK_NBLINT = BUILD / "nblint.ok.d"
OK_PIP_INSTALL = BUILD / "pip_install.ok"
OK_PRETTIER = BUILD / "prettier.ok"

# derived info
PY_VERSION = re.findall(r'''__version__ = "(.*)"''', VERSION_PY.read_text())[0]

# built artifacts
SDIST = DIST / f"ipyradiant-{PY_VERSION}.tar.gz"
WHEEL = DIST / f"ipyradiant-{PY_VERSION}-py3-none-any.whl"
HASH_DEPS = [SDIST, WHEEL]
SHA256SUMS = DIST / "SHA256SUMS"
EXAMPLE_HTML = [BUILD_NBHTML / p.name.replace(".ipynb", ".html") for p in EXAMPLE_IPYNB]
