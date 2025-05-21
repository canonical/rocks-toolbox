// Package rmadison displays information about Debian packages using the
// rmadison(1) tool. On Ubuntu, it comes in the devscripts package.
package rmadison

import (
	"context"
	"fmt"
	"log"
	"os/exec"
	"strings"
)

type QueryOptions struct {
	Arch      []string
	Component []string
	Suite     []string
	Package   []string
}

// Query performs a "rmadison .." command query. It returns the stdout as a
// string if there are no errors. Otherwise, it returns an error.
func Query(opts *QueryOptions) ([]*Result, error) {
	log.Print("Querying the remote archive(s)...")
	cmd := exec.Command("rmadison", cmdArgs(opts)...)
	out, err := cmd.Output()
	if err != nil {
		return nil, err
	}
	return formatOutput(string(out))
}

// QueryWithContext is similar to [Query], except it takes a context in addition
// to interrupt the execution if needed.
func QueryWithContext(ctx context.Context, opts *QueryOptions) ([]*Result, error) {
	log.Println("Querying the remote archive(s)...")
	cmd := exec.CommandContext(ctx, "rmadison", cmdArgs(opts)...)
	out, err := cmd.Output()
	if err != nil {
		return nil, err
	}
	return formatOutput(string(out))
}

func cmdArgs(opts *QueryOptions) []string {
	var args []string
	if opts == nil {
		return args
	}
	if len(opts.Arch) > 0 {
		args = append(args, "-a", strings.Join(opts.Arch, ","))
	}
	if len(opts.Component) > 0 {
		args = append(args, "-c", strings.Join(opts.Component, ","))
	}
	if len(opts.Suite) > 0 {
		args = append(args, "-s", strings.Join(opts.Suite, ","))
	}
	args = append(args, opts.Package...)
	return args
}

// The result entries have 4 fields separated by a vertical bar ("|") - package
// name, version, suite(s), arch(s).
type Result struct {
	Package string
	Version string
	Suite   string
	Arch    string
}

func parse(s string) (*Result, error) {
	parts := strings.Split(s, "|")
	if len(parts) != 4 {
		return nil, fmt.Errorf("invalid format: %s", s)
	}
	for i := range parts {
		parts[i] = strings.TrimSpace(parts[i])
	}
	return &Result{
		Package: parts[0],
		Version: parts[1],
		Suite:   parts[2],
		Arch:    parts[3],
	}, nil
}

func formatOutput(s string) ([]*Result, error) {
	s = strings.TrimSpace(s)
	lines := strings.Split(s, "\n")
	var res []*Result
	for _, l := range lines {
		l = strings.TrimSpace(l)
		if l == "" {
			continue
		}
		r, err := parse(l)
		if err != nil {
			return nil, fmt.Errorf("cannot format output: %w", err)
		}
		res = append(res, r)
	}
	return res, nil
}
