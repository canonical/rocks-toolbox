import argparse
import logging
from pathlib import Path

from .config.base import YAMLCheckConfigBase

# TODO: display all available configs in help
parser = argparse.ArgumentParser()

parser.add_argument(
    "-v", "--verbose", action="store_true", help="Enable verbose output."
)

parser.add_argument(
    "-w", "--write", action="store_true", help="Write yaml output to disk."
)

parser.add_argument(
    "--config",
    type=str,
    default="YAMLCheckConfigBase",
    help="CheckYAML subclass to load",
)

parser.add_argument(
    "files", type=Path, nargs="*", help="Additional files to process (optional)."
)


def main():
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    check_yaml_config = YAMLCheckConfigBase.configs[args.config]

    yaml = check_yaml_config()

    for file in args.files:
        data = yaml.load(file.read_text())
        data = yaml.apply_rules(data)
        yaml.validate_model(data)

        output = yaml.dump(data)

        if args.write:
            file.write_text(output)
        else:
            print(output)


if __name__ == "__main__":
    main()
