# oci-factory_workflows

The oci-factory includes several reusable workflows that can be adapted for
other CI tasks related to rocks. This directory provides documentation and
examples to guide their use.


## Build-Rock

The Build-Rock workflow is capable of building multi architecture rocks. Github
Runners in the required target architecture must be available and configured
when calling this workflow. Alternatively, builds can be executed remotely on
the Launchpad CI platform if available.

**Examples:**
- Building an External Rock - ./examples/Build_External_Rock.yaml