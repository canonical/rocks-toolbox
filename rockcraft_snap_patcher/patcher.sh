#! /bin/bash

# Rockcraft snap package patcher
# Version 4

set -xe

# configurable vars
src_snap="rockcraft_1.5.3.post51+gc99aa44.d20241011_amd64.snap" # snap package to modify
rockcraft="." # Path to rockcraft repo
craft_application="../craft-application/" # Path to craft_application repo
craft_providers="../craft-providers/"  # Path to craft_providers repo
craft_parts="../craft-parts/"  # Path to craft_providers repo


# setup
snap_rootfs=$(mktemp -d -p "./.patcher/")
sudo mkdir -p "$snap_rootfs"

# unpack rootfs
unsquashfs -f -d "$snap_rootfs" "$src_snap"
snap_name=$(yq '.name' "$snap_rootfs/meta/snap.yaml")
# snap_src_version=$(yq '.version' "$snap_rootfs/meta/snap.yaml")
snap_arch=$(yq '.architectures[0]' "$snap_rootfs/meta/snap.yaml") #TODO: support multi arch?
snap_python_bin=$(readlink -f "$snap_rootfs/bin/python")
snap_python_name=$(basename $snap_python_bin) # used in locating craft libraries


# modify snap rootfs
rm -rf "$snap_rootfs/lib/$snap_python_name/site-packages/rockcraft"
rsync -r --chown=root:root "$rockcraft/rockcraft" "$snap_rootfs/lib/$snap_python_name/site-packages/"

rm -rf "$snap_rootfs/lib/$snap_python_name/site-packages/craft_application"
rsync -r --chown=root:root "$craft_application/craft_application" "$snap_rootfs/lib/$snap_python_name/site-packages/"

rm -rf "$snap_rootfs/lib/$snap_python_name/site-packages/craft_parts"
rsync -r --chown=root:root "$craft_parts/craft_parts" "$snap_rootfs/lib/$snap_python_name/site-packages/"

rm -rf "$snap_rootfs/lib/$snap_python_name/site-packages/craft_providers"
rsync -r --chown=root:root "$craft_providers/craft_providers" "$snap_rootfs/lib/$snap_python_name/site-packages/"

# repack and install snap rootfs
export snap_dst_version="local-patch-$(date +%s)"
yq e -i ".version= env(snap_dst_version)" "$snap_rootfs/meta/snap.yaml"
dst_snap="${snap_name}_${snap_dst_version}_${snap_arch}.snap"

rm -f "$dst_snap"
mksquashfs "$snap_rootfs" "$dst_snap" -noappend -comp lzo -no-fragments
sudo snap install "$dst_snap" --dangerous --classic

# cleanup
rm -rf "$snap_rootfs"
