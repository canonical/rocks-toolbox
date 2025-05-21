package chisel_test

import (
	"os"
	"reflect"
	"testing"

	"github.com/canonical/rocks-toolbox/chisel-tools/internal/chisel"
)

const sampleChiselYaml = `
archives:
  foo:
    suites: [a, b, c]
    components: [p, q, r]
v2-archives:
  bar:
    suites: [x]
    components: [y, z]
`

var chiselYamlTests = []struct {
	summary string
	data    string
	config  *chisel.Config
}{{
	summary: "Sample chisel.yaml",
	data:    sampleChiselYaml,
	config: &chisel.Config{
		Archives: map[string]*chisel.Archive{
			"foo": {
				Suites:     []string{"a", "b", "c"},
				Components: []string{"p", "q", "r"},
			},
			"bar": {
				Suites:     []string{"x"},
				Components: []string{"y", "z"},
			},
		},
	},
}}

func TestParseConfig(t *testing.T) {
	for _, tc := range chiselYamlTests {
		f, err := os.CreateTemp("", "chisel.yaml")
		if err != nil {
			t.Fatal("cannot create temporary file")
		}
		defer os.Remove(f.Name())

		f.WriteString(tc.data)
		defer f.Close()

		cfg, err := chisel.ParseConfig(f.Name())
		if err != nil {
			t.Fatal(err)
		}
		if !reflect.DeepEqual(cfg, tc.config) {
			t.Fatalf("have %v, want %v", cfg, tc.config)
		}
	}
}
