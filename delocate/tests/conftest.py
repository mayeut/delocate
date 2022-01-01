import os
import subprocess
from pathlib import Path
from typing import Iterator

import pytest
from delocate.tools import set_install_name
from delocate.wheeltools import InWheelCtx

from .test_wheelies import PLAT_WHEEL, STRAY_LIB_DEP, PlatWheel


@pytest.fixture
def plat_wheel(tmp_path: Path) -> Iterator[PlatWheel]:
    """Return a modified platform wheel for testing."""
    plat_wheel_tmp = str(tmp_path / "plat-wheel.whl")
    stray_lib: str = STRAY_LIB_DEP

    with InWheelCtx(PLAT_WHEEL, plat_wheel_tmp):
        set_install_name(
            "fakepkg1/subpkg/module2.abi3.so",
            "libextfunc.dylib",
            stray_lib,
        )

    yield PlatWheel(plat_wheel_tmp, os.path.realpath(stray_lib))


def _get_xcode_installs():
    applications = Path("/Applications")
    if applications.exists():
        result = set()
        for path in applications.glob("Xcode_*.app"):
            result.add(path.resolve(strict=True).stem)
        return sorted(result)
    return []


@pytest.fixture(
    scope="session", autouse=True, params=["default", *_get_xcode_installs()]
)
def all_xcode_versions(request, tmp_path_factory):
    if request.param == "default":
        yield
    else:
        developer_dir = f"/Applications/{request.param}.app/Contents/Developer"
        env = os.environ.copy()
        env["DEVELOPER_DIR"] = developer_dir
        tmp_path = tmp_path_factory.mktemp(f"{request.param}-tools")
        for tool_name in {"otool", "lipo", "install_name_tool", "codesign"}:
            link = tmp_path / tool_name
            tool = subprocess.run(
                ["xcrun", "--find", tool_name],
                check=True,
                env=env,
                universal_newlines=True,
                stdout=subprocess.PIPE,
            ).stdout.strip()
            link.symlink_to(tool)
            link.lchmod(0o755)

        prev_path = os.environ["PATH"]
        prev_developer_dir = os.environ.get("DEVELOPER_DIR", None)
        os.environ["PATH"] = f"{tmp_path}:{prev_path}"
        os.environ["DEVELOPER_DIR"] = developer_dir
        try:
            yield
        finally:
            os.environ["PATH"] = prev_path
            if prev_developer_dir is not None:
                os.environ["DEVELOPER_DIR"] = prev_developer_dir
            else:
                del os.environ["DEVELOPER_DIR"]
