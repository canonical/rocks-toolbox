from typing import Any, Dict, List

from pydantic import BaseModel, Field, RootModel
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.scalarstring import PlainScalarString

from .base import YAMLCheckConfigBase


class Slices(RootModel):
    # TODO: expand slices model to validate individual slices
    root: Dict[str, Any]


class SDF(BaseModel):
    package: str = Field()
    essential: List[str] = Field()
    slices: Slices = Field()

    model_config = {"extra": "forbid"}


class Chisel(YAMLCheckConfigBase):
    rules = {
        "/slices/*/essential": "sort_content",
        "/slices/*/essential/*": "no_quotes",
        "/slices/*/contents": "sort_content",
    }

    def sort_content(self, path, data):
        """Sort dict and list objects."""

        def prep_comment_content(value):
            # remove whitespace and leading pound sign
            value = value.strip()
            value = value.strip("#")
            return value

        if isinstance(data, dict):
            sorted_dict = CommentedMap()
            for key in sorted(data.keys()):
                sorted_dict[key] = data[key]

                if key in data.ca.items:
                    _, key_comments, eol_comment, _ = data.ca.items[key]

                    # Migrate comments to new sorted dictionary. This works for most
                    # but not all cases
                    if key_comments is not None:
                        if not isinstance(key_comments, list):
                            key_comments = [key_comments]

                        for key_comment in key_comments:
                            content = prep_comment_content(key_comment.value)
                            sorted_dict.yaml_set_comment_before_after_key(
                                key, before=content, indent=key_comment.column
                            )

                    if eol_comment is not None:
                        # These should be sorted ok, no need for warning
                        content = prep_comment_content(eol_comment.value)
                        sorted_dict.yaml_add_eol_comment(content, key)

            return sorted_dict

        elif isinstance(data, list):
            data.sort()
            return data

        return data

    def no_quotes(self, path, data):
        """Remove quotes form strings"""
        if isinstance(data, str):
            return PlainScalarString(data)

        return data

    # validate documents with basic SDF model
    Model = SDF
