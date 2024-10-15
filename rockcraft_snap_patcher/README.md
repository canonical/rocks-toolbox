# Rockcraft Patcher

`patcher.sh` enables quick rockcraft "builds" for development by patching 
an existing snap package with changes made to dependancies on the local
system.  

## How to use

0. Clone rockcraft, craft-application, craft-providers and craft-parts.
1. Build a Rockcraft snap package to use as a donor for the patched package.
2. Place the the `patcher.sh` sciprt in the rockcraft source directory.
3. Edit the paths in the script to point to the other craft repositories on 
your system as well as the donor package.
4. Run `patcher.sh` to create the patched package and install it to the system.
The installation can be verified by checking `snap list`. Rockcraft should show
a version number similar to `local-patch-<timestamp>`.

`patcher.sh` can be run as needed for testing changes made to the local repos. 

## TODO: 
- Support debugging Python in rockcraft. Include VSCodes launch.json