# oci-factory workflows

The [oci-factory](https://github.com/canonical/oci-factory) features several
reusable workflows that can be adapted for other Rock oriented CI tasks. This
rocks-toolbox provides documentation and examples to guide their use in other
projects.


## Build-Rock Workflow

The Build-Rock workflow is capable of building multi architecture rocks. Github
Runners in the required target architecture must be available and configured
when calling this workflow. Alternatively, builds can be executed remotely on
the Launchpad CI platform if available.

**Examples:**
- Building an External Rock - ./examples/Build_External_Rock.yaml


## Test-Rock Workflow

In oci-factory, automated testing of built rocks is completed with the Test-Rock
workflow. This test several aspects including:
- Testing OCI Compliance of Rock images
- Testing image storage efficiency using [Dive](https://github.com/wagoodman/dive)
- Scanning for vulnerabilities using [trivy](https://trivy.dev/)
- Scanning for malware using [ClamAV](https://www.clamav.net/)

test-oci-compliance:
        description: 'Enable compliance test.'
        default: true
        type: boolean
      test-efficiency:
        description: 'Enable efficiency test.'
        default: true
        type: boolean
      test-vulnerabilities:
        description: 'Enable vulnerability test.'
        default: true
        type: boolean
      test-malware:
        description: 'Enable malware test.'
        default: true
        type: boolean 

**Examples:**
- Test a rock containing a EICAR test file to demonstrate test failures  - ./examples/Test_External_Rock.yaml