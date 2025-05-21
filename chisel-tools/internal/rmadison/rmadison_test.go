package rmadison_test

import (
	"reflect"
	"testing"

	"github.com/canonical/rocks-toolbox/chisel-tools/internal/rmadison"
)

const sampleOut = `
 hello | 2.10-1build3  | bionic-updates  | source, amd64, i386, ppc64el, s390x
 libc6 | 2.10-2ubuntu2 | focal           | source, arm64, armhf, riscv64
`

var formatOutputTests = []struct {
	output string
	result []*rmadison.Result
	err    string
}{{
	output: sampleOut,
	result: []*rmadison.Result{{
		"hello", "2.10-1build3", "bionic-updates", "source, amd64, i386, ppc64el, s390x",
	}, {
		"libc6", "2.10-2ubuntu2", "focal", "source, arm64, armhf, riscv64",
	}},
}, {
	output: "",
}, {
	output: "\n\n\n",
}, {
	output: "foo | bar | baz",
	err:    "cannot format output: invalid format: foo | bar | baz",
}}

func TestFormatOutput(t *testing.T) {
	for _, tc := range formatOutputTests {
		res, err := rmadison.FormatOutput(tc.output)
		if tc.err != "" {
			if err.Error() != tc.err {
				t.Fatalf("have error %q, want %q", err, tc.err)
			}
			continue
		} else {
			if err != nil {
				t.Fatalf("have error %s, want nil", err)
			}
		}
		if !reflect.DeepEqual(res, tc.result) {
			t.Fatalf("have %v, want %v", res, tc.result)
		}
	}
}

var cmdArgsTests = []struct {
	opts *rmadison.QueryOptions
	args []string
}{{
	opts: &rmadison.QueryOptions{
		Arch:      []string{"amd64", "armhf"},
		Component: []string{"main", "universe"},
		Suite:     []string{"focal", "jammy"},
		Package:   []string{"hello", "libc6"},
	},
	args: []string{
		"-a", "amd64,armhf",
		"-c", "main,universe",
		"-s", "focal,jammy",
		"hello",
		"libc6",
	},
}, {
	opts: &rmadison.QueryOptions{
		Arch:      []string{"amd64"},
		Component: []string{"main"},
		Suite:     []string{"focal"},
		Package:   []string{"hello", "libc6"},
	},
	args: []string{
		"-a", "amd64",
		"-c", "main",
		"-s", "focal",
		"hello",
		"libc6",
	},
}, {
	opts: &rmadison.QueryOptions{
		Package: []string{"hello"},
	},
	args: []string{"hello"},
}, {
	opts: &rmadison.QueryOptions{},
	args: nil,
}, {
	opts: nil,
	args: nil,
}}

func TestCmdArgs(t *testing.T) {
	for _, tc := range cmdArgsTests {
		args := rmadison.CmdArgs(tc.opts)
		if !reflect.DeepEqual(args, tc.args) {
			t.Fatalf("have %v, want %v", args, tc.args)
		}
	}
}
