from pathlib import Path
from setuptools import setup, find_packages


def read(filename):
    filepath = Path(__file__).parent / filename
    file = open(filepath, "r")
    return file.read()


setup(
    name="yaml_checker",
    version="0.1.0",
    long_description=read("README.md"),
    packages=find_packages(),
    install_requires=read("requirements.txt"),
)
