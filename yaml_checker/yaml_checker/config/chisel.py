from ruyaml.scalarstring import PlainScalarString
from ruyaml.comments import CommentedMap

from pydantic import BaseModel, Field, RootModel
from typing import List, Dict, Any


from .base import YAMLCheckConfigBase


class Slices(RootModel):
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
        # print(path, type(data))
        # print(dir(data))
        # print()
        # return CommentedMap(sorted(data))

        if isinstance(data, dict):
            # data.ordereddict()
            print(path, type(data), str(data))
            print(data.ca.items)
            # print(dir(data))
            sorted_dict = CommentedMap()
            for key, value in data.items():
                # print(key, "before", data.get_comment_inline(key))

                sorted_dict[key] = data[key]

            return sorted_dict

            # sorted_items = sorted(
            #     data.items(),
            #     key=lambda item: item[0],  # Sort by key
            # )

            # sorted_settings = CommentedMap()
            # for key, value in sorted_items:
            #     # Attach comments manually
            #     if isinstance(value, dict) and isinstance(value, CommentedMap):
            #         sorted_settings[key] = value
            #     else:
            #         sorted_settings[key] = value

            # # print(dir(data))

            # return sorted_settings

        elif isinstance(data, list):
            data.sort()
            return data

        return data

    def no_quotes(self, path, data):
        if isinstance(data, str):
            return PlainScalarString(data)

        return data

    Model = SDF
