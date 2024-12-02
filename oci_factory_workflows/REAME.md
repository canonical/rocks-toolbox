# oci-factory workflows

The [oci-factory](https://github.com/canonical/oci-factory) provides reusable
GitHub workflows designed to support Rock-oriented CI tasks. This directory
includes documentation and examples to help integrate these workflows into your
projects.


## Build-Rock Workflow

The [Build-Rock workflow](https://github.com/canonical/oci-factory/blob/main/.github/workflows/Build-Rock.yaml)
can create multi-architecture Rocks (OCI images) from a specified Rockcraft
project file (rockcraft.yaml). This project file can be located in the
repository initiating the workflow, an external repository hosted on GitHub, or
a Git repository hosted elsewhere. The resulting image is uploaded as a build
artifact in the GitHub workflow. Currently, multi-architecture builds support
AMD64 and ARM64, depending on the availability of GitHub runners for these
architectures. Additional architectures, such as PPC64EL and S390X, are
supported through Launchpad build services.

**Samples:**
- [Building an Simple Rock](oci_factory_workflows/samples/build_mock_rock.yaml) 
  - Build the "Mock Rock" located in `mock_rock/1.0`
- [Build and Test EICAR Rock](oci_factory_workflows/samples/build_and_test_eicar_rock.yaml) 
  - Build a Rock that includes the
    [EICAR test file](https://en.wikipedia.org/wiki/EICAR_test_file) and run the
    Test-Rock workflow on it. The workflow is expected to fail during the
    malware scan for demonstration purposes.
- [Building an external Rock](oci_factory_workflows/samples/build_external_rock.yaml)
  - Build a Chiseled-Python Rock from an external repository using a specified Git commit hash.

**Workflow Inputs:**
- `oci-archive-name`
  - Final filename of the rock OCI archive.
  - Type: string
  - Required
- `build-id`
  - Optional string for identifying workflow jobs in GitHub UI
  - Type: string
  - Optional, default: `""`
- `rock-repo`
  - Public Git repo where to build the rock from.
  - Type: string
  - Required
- `rock-repo-commit`
  - Git ref from where to build the rock from.
  - Type: string
  - Required
- `rockfile-directory`
  - Directory in repository where to find the rockcraft.yaml file.
  - Type: string
  - Required
- `arch-map`
  - JSON string mapping target architecture to runners.
  - Type: string
  - Optional, default: `'{"amd64": ["linux", "X64"], "arm64": ["linux", "ARM64"]}'`
- `lpci-fallback`
  - Enable fallback to Launchpad build when runners for target arch are not available.
  - Type: boolean
  - Optional, default: `false`


## Test-Rock Workflow

The [Test-Rock workflow](https://github.com/canonical/oci-factory/blob/main/.github/workflows/Test-Rock.yaml)
runs a series of tests on a Rock or OCI image. The image can be sourced either
from a local artifact or from an external location uploaded as an artifact. The
workflow includes the following tests, which can be enabled or disabled as
needed.

- OCI compliance testing of images using [Umoci](https://umo.ci/). The image's
  readability and layout are tested by unpacking and listing the image tags.
- Black-box testing of images performed using Docker to create a container and
  attempting to run the Pebble service manager. This test applies only to
  images created with Rockcraft.
- Testing image storage efficiency using [Dive](https://github.com/wagoodman/dive)
- Scanning for vulnerabilities using [trivy](https://trivy.dev/)
- Scanning for malware using [ClamAV](https://www.clamav.net/)

**Samples:**
- [Build and Test EICAR Rock](oci_factory_workflows/samples/build_and_test_eicar_rock.yaml) 
  - Build a Rock that includes the
    [EICAR test file](https://en.wikipedia.org/wiki/EICAR_test_file) and run the
    Test-Rock workflow on it. The workflow is expected to fail during the
    malware scan for demonstration purposes.

**Workflow Inputs:**
- `oci-archive-name`
  - Artifact name to download for testing.
  - required
  - type: string
- `test-oci-compliance`
  - Enable Umoci OCI Image compliance test.
  - optional, default: `true`
  - type: boolean
- `test-oci-compliance`
  - Enable Umoci OCI Image compliance test.
  - optional, default: `true`
  - type: boolean
- `test-efficiency`
  - Enable Dive image efficiency test.
  - optional, default: `true`
  - type: boolean
- `test-vulnerabilities`
  - Enable Trivy vulnerability test.
  - optional, default: `true`
  - type: boolean
- `trivyignore-path`
  - Optional path to `.trivyignore` file used in vulnerability scan.
  - optional, default: `""`
  - type: string
- `test_malware`
  - Enable ClamAV malware test.
  - optional, default: `true`
  - type: boolean
