package chisel

import (
	"fmt"
	"os"

	"gopkg.in/yaml.v3"
)

// chisel.yaml, for a lack of a better name, is the config for Chisel.
// The "v2-archives" field will be merged into "archives" after parsing.
type Config struct {
	Archives   map[string]*Archive `yaml:"archives"`
	V2Archives map[string]*Archive `yaml:"v2-archives"`
	// TODO add remaining fields when necessary.
}

type Archive struct {
	Suites     []string `yaml:"suites"`
	Components []string `yaml:"components"`
	// TODO add remaining fields when necessary.
}

// Parse the chisel.yaml file given it's path.
func ParseConfig(path string) (*Config, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	cfg := &Config{}
	d := yaml.NewDecoder(f)
	if err := d.Decode(cfg); err != nil {
		return nil, err
	}

	for k, v := range cfg.V2Archives {
		cfg.Archives[k] = v
		delete(cfg.V2Archives, k)
	}
	cfg.V2Archives = nil

	if len(cfg.Archives) == 0 {
		return nil, fmt.Errorf("no 'archives' specified")
	}
	for name, a := range cfg.Archives {
		if len(a.Suites) == 0 {
			return nil, fmt.Errorf("archive %s has no 'suites'", name)
		}
		if len(a.Components) == 0 {
			return nil, fmt.Errorf("archive %s has no 'components'", name)
		}
	}
	return cfg, nil
}
