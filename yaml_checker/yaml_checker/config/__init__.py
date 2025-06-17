from importlib import import_module
from pathlib import Path

submodule_root = Path(__file__).parent
package_name = __name__

# import all submodules so our configs registry is populated
for submodule in submodule_root.glob("*.py"):
    submodule_name = submodule.stem

    if submodule_name.startswith("_"):
        continue

    import_module(f"{__name__}.{submodule_name}")
