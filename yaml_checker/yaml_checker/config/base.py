import fnmatch
import logging
from io import StringIO
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from ruamel.yaml import YAML


class YAMLCheckConfigReg(type):
    def __init__(cls, *args, **kwargs):
        """Track all subclass configurations of YAMLCheckConfigBase  for CLI"""
        super().__init__(*args, **kwargs)
        name = cls.__name__
        if name not in cls.configs:
            cls.configs[name] = cls


class YAMLCheckConfigBase(metaclass=YAMLCheckConfigReg):
    configs = {}  # Store configs for access from CLI
    rules = {}  # map glob strings to class method names

    class Model(BaseModel):
        """Pydantic BaseModel to provide validation"""

        class Config:
            extra = "allow"

    class Config:
        """ruamel.yaml configuration set before loading."""

        preserve_quotes = True
        width = 80
        map_indent = 2
        sequence_indent = 4
        sequence_dash_offset = 2

    def __init__(self):
        """YAMLCheck Base Config"""
        self.yaml = YAML()

        # load Config into yaml
        for attr in dir(self.Config):
            if attr.startswith("__"):
                continue

            attr_val = getattr(self.Config, attr)

            if hasattr(self.yaml, attr):
                setattr(self.yaml, attr, attr_val)
            else:
                raise AttributeError(f"Invalid ruamel.yaml attribute: {attr}")

    def load(self, yaml_str: str):
        """Load YAML data from string"""
        data = self.yaml.load(yaml_str)

        return data

    def dump(self, data: Any):
        """Dump data to YAML string"""
        with StringIO() as sio:
            self.yaml.dump(data, sio)
            sio.seek(0)

            return sio.read()

    def validate_model(self, data: Any):
        """Apply validate data against model"""
        if issubclass(self.Model, BaseModel):
            _ = self.Model(**data)

    def _apply_rules(self, path: Path, data: Any):
        """Recursively apply rules starting from the outermost elements."""
        logging.debug(f"Walking path {path}.")

        # recurse over dicts and lists
        if isinstance(data, dict):
            for key, value in data.items():
                data[key] = self._apply_rules(path / str(key), value)

        elif isinstance(data, list):
            for index, item in enumerate(data):
                data[index] = self._apply_rules(path / str(item), item)

        # scan for applicable rules at each directory
        # TODO: selection of rules here does not scale well and should be improved
        for key, value in self.rules.items():
            if fnmatch.fnmatch(path, key):
                logging.debug(f'Applying rule "{value}" at {path}')
                rule = getattr(self, value)
                data = rule(path, data)

        return data

    def apply_rules(self, data: Any):
        """Walk all objects in data and apply rules where applicable."""
        return self._apply_rules(Path("/"), data)
