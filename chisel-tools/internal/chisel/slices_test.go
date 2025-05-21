package chisel_test

import (
	"os"
	"reflect"
	"testing"

	"github.com/canonical/rocks-toolbox/chisel-tools/internal/chisel"
)

const sampleSlice = `
package: foo
essential:
  - bar_foo
slices:
  foo:
    essential:
      - bar_bar
  bar:
    essential:
      - foo_foo
      - buz_foo
    extra: # extra field, must be ignored
      - foo
extra: # extra field, must be ignored.
  foo: bar
`

var sliceData = []struct {
	summary string
	data    string
	slices  []*chisel.Slice
}{{
	summary: "Sample slice definition file",
	data:    sampleSlice,
	slices: []*chisel.Slice{{
		Name:      "foo_bar",
		Package:   "foo",
		Essential: []string{"foo_foo", "buz_foo", "bar_foo"},
	}, {
		Name:      "foo_foo",
		Package:   "foo",
		Essential: []string{"bar_bar", "bar_foo"},
	}},
}}

func TestParseSliceDef(t *testing.T) {
	for _, tc := range sliceData {
		t.Logf("Summary: %s", tc.summary)

		f, err := os.CreateTemp("", "slice")
		if err != nil {
			t.Fatal("cannot create temporary file")
		}
		defer os.Remove(f.Name())

		f.WriteString(tc.data)
		defer f.Close()

		slices, err := chisel.ParseSlices(f.Name())
		if err != nil {
			t.Fatal(err)
		}
		if !reflect.DeepEqual(slices, tc.slices) {
			t.Fatalf("have %v, want %v", slices, tc.slices)
		}
	}
}
