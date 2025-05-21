package main_test

import (
	"reflect"
	"testing"

	sdf "github.com/canonical/rocks-toolbox/chisel-tools/cmd/sdf"
	"github.com/canonical/rocks-toolbox/chisel-tools/internal/chisel"
	"github.com/canonical/rocks-toolbox/chisel-tools/internal/rmadison"
)

var pruneTests = []struct {
	slices []*chisel.Slice
	pruned []string
}{{
	slices: []*chisel.Slice{{
		Name: "pkg1_slice1",
		Essential: []string{
			"pkg2_slice1",
			"pkg1_slice2",
		},
	}, {
		Name: "pkg1_slice2",
	}, {
		Name: "pkg2_slice1",
		Essential: []string{
			"pkg1_slice2",
		},
	}, {
		Name: "pkg3_slice1",
	}},
	pruned: []string{
		"pkg1_slice1",
		"pkg3_slice1",
	},
}}

func TestPrune(t *testing.T) {
	for _, tc := range pruneTests {
		slices := sdf.Prune(tc.slices)
		var pruned []string
		for _, s := range slices {
			pruned = append(pruned, s.Name)
		}
		if !reflect.DeepEqual(pruned, tc.pruned) {
			t.Fatalf("have %v, want %v", pruned, tc.pruned)
		}
	}
}

var ensureIgnoreTests = []struct {
	slices    []*chisel.Slice             // List of slices to ensure, or ignore missing.
	pkgs      map[string]*rmadison.Result // Package info from rmadison query.
	arch      string                      // Package arch to ignore missing for.
	ensureErr string                      // Expected ensure-existing errors.
	found     []*chisel.Slice             // Expected slices which are not to be ignored.
}{{
	slices: []*chisel.Slice{{
		Name:    "hello_bins",
		Package: "hello",
	}, {
		Name:    "hello_copyright",
		Package: "hello",
	}, {
		Name:    "python3_core",
		Package: "python3",
	}, {
		Name:    "libc6_libs",
		Package: "libc6",
	}, {
		Name:    "java_extra",
		Package: "java",
	}},
	pkgs: map[string]*rmadison.Result{
		"hello": {
			Arch: "amd64, arm64, i386",
		},
		"libc6": {
			Arch: "all",
		},
		"java": {
			Arch: "arm64, i386",
		},
	},
	arch:      "amd64",
	ensureErr: `package "python3" does not exist`,
	found: []*chisel.Slice{{
		Name:    "hello_bins",
		Package: "hello",
	}, {
		Name:    "hello_copyright",
		Package: "hello",
	}, {
		Name:    "libc6_libs",
		Package: "libc6",
	}},
}}

func TestEnsurePackages(t *testing.T) {
	for _, tc := range ensureIgnoreTests {
		err := sdf.EnsurePackages(tc.slices, tc.pkgs)
		if tc.ensureErr != "" {
			if err.Error() != tc.ensureErr {
				t.Fatalf("have error %q, want %q", err, tc.ensureErr)
			}
		} else {
			if err != nil {
				t.Fatalf("have error %q, want nil", err)
			}
		}
	}
}

func TestIgnoreMissing(t *testing.T) {
	for _, tc := range ensureIgnoreTests {
		slices := sdf.IgnoreMissing(tc.slices, tc.pkgs, tc.arch)
		if !reflect.DeepEqual(slices, tc.found) {
			t.Fatalf("have %v, want %v", slices, tc.found)
		}
	}
}
