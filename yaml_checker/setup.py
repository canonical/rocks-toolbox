from pathlib import Path

from setuptools import find_packages, setup


def read_text(filename):
    filepath = Path(__file__).parent / filename
    return filepath.read_text()


setup(
    name="yaml_checker",
    version="0.1.0",
    long_description=read_text("README.md"),
    packages=find_packages(),
    install_requires=read_text("requirements.txt"),
    entry_points={
        "console_scripts": [
            "yaml_checker=yaml_checker.__main__:main",
            "clayaml=yaml_checker.__main__:main",
        ],
    },
)
