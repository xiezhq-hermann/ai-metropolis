"""Build the C++ extension. Package metadata lives in pyproject.toml."""
import os
import shutil
import subprocess

import pybind11
from setuptools import Extension, setup


def hiredis_paths():
    """Find hiredis: HIREDIS_PREFIX, then pkg-config, then the compiler defaults and Homebrew."""
    prefix = os.environ.get("HIREDIS_PREFIX")
    if prefix:
        return [os.path.join(prefix, "include")], [os.path.join(prefix, "lib")]

    if shutil.which("pkg-config"):
        try:
            cflags = subprocess.check_output(["pkg-config", "--cflags-only-I", "hiredis"], text=True).split()
            libs = subprocess.check_output(["pkg-config", "--libs-only-L", "hiredis"], text=True).split()
        except subprocess.CalledProcessError:
            pass
        else:
            # the sources include <hiredis/hiredis.h>, but some .pc files point inside that directory
            includes = [flag[2:].rstrip("/") for flag in cflags]
            includes = [os.path.dirname(path) if path.endswith("/hiredis") else path for path in includes]
            return includes, [flag[2:] for flag in libs]

    brew_prefix = "/opt/homebrew"
    if os.path.isdir(os.path.join(brew_prefix, "include", "hiredis")):
        return [os.path.join(brew_prefix, "include")], [os.path.join(brew_prefix, "lib")]
    return [], []


include_dirs, library_dirs = hiredis_paths()

setup(ext_modules=[
    Extension("aimetropoliscpp",
              sources=["csrc/persona_dependency.cpp"],
              include_dirs=[pybind11.get_include(), *include_dirs],
              library_dirs=library_dirs,
              libraries=["hiredis"],
              extra_compile_args=["-std=c++17"],
              language="c++")
])
