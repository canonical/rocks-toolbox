import logging
from ruyaml.scalarstring import SingleQuotedScalarString, DoubleQuotedScalarString

from .base import YAMLCheckConfigBase


class OCIFactory(YAMLCheckConfigBase):
    rules = {"/**": "convert_to_single_quotes"}

    def convert_to_single_quotes(self, path, data):
        # filter out only strings of DoubleQuotedScalarString
        if isinstance(data, DoubleQuotedScalarString):
            # skip strings containing "'" character
            if "'" in data:
                logging.warning(f'Cannot convert {path}, contains "\'" character.')
                return data

            return SingleQuotedScalarString(data)

        # fall back
        return data
