package chisel

import (
	"fmt"
	"os"
	"sort"
	"strings"

	"gopkg.in/yaml.v3"
)

// The interesting bits about a chisel slice.
type Slice struct {
	Name      string   `yaml:"-"`
	Package   string   `yaml:"-"`
	Essential []string `yaml:"essential,omitempty"`
	// TODO add remaining fields when necessary.
}

type sliceDef struct {
	Package   string           `yaml:"package"`
	Essential []string         `yaml:"essential,omitempty"`
	Slices    map[string]Slice `yaml:"slices"`
}

// Parse all slices from a slice definition file.
func ParseSlices(path string) ([]*Slice, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	def := &sliceDef{}
	d := yaml.NewDecoder(f)
	if err := d.Decode(def); err != nil {
		return nil, err
	}

	if def.Package == "" {
		return nil, fmt.Errorf("missing 'package' field")
	}
	if len(def.Slices) == 0 {
		return nil, fmt.Errorf("missing 'slices' field")
	}
	for _, s := range def.Essential {
		if _, _, err := Parse(s); err != nil {
			return nil, fmt.Errorf("'essential': %w", err)
		}
	}

	var slices []*Slice
	for name, slice := range def.Slices {
		for _, e := range slice.Essential {
			if _, _, err := Parse(e); err != nil {
				return nil, fmt.Errorf("slice %s 'essential': %w", name, err)
			}
		}
		slice.Essential = append(slice.Essential, def.Essential...)
		slice.Name = Name(def.Package, name)
		slice.Package = def.Package
		slices = append(slices, &slice)
	}
	sort.Slice(slices, func(i, j int) bool {
		return slices[i].Name < slices[j].Name
	})
	return slices, nil
}

func Name(pkg, slice string) string {
	return pkg + "_" + slice
}

func Parse(name string) (pkg, slice string, err error) {
	i := strings.Index(name, "_")
	if i < 0 {
		return "", "", fmt.Errorf("invalid slice name: %s", name)
	}
	pkg, slice = name[:i], name[i+1:]
	if strings.Contains(slice, "_") {
		return "", "", fmt.Errorf("invalid slice name: %s", name)
	}
	return pkg, slice, nil
}
