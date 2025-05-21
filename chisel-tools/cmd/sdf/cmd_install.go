package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/canonical/rocks-toolbox/chisel-tools/internal/chisel"
	"github.com/canonical/rocks-toolbox/chisel-tools/internal/rmadison"
)

const (
	tick  = '\u2713'
	cross = '\u2717'
)

type cmdInstall struct {
	Release string `short:"r" long:"release" description:"Chisel release path" required:"true"`
	Arch    string `short:"a" long:"arch" description:"Package architecture" default:"amd64"`
	Workers int    `short:"w" long:"workers" description:"Number of concurrent workers" default:"10"`

	// You may use [Combine] and [Prune] together. The slices will be pruned
	// first and then combined to install only the top level slices in one go.
	Combine bool `long:"combine" description:"Install all slices in one go"`
	Prune   bool `long:"prune" description:"Install only the top level slices"`

	Continue bool `short:"c" long:"continue-on-error" description:"Continue on installation errors"`
	Ignore   bool `long:"ignore-missing" description:"Ignore missing packages for an arch"`
	Ensure   bool `long:"ensure-existence" description:"Ensure package existence for at least one arch"`

	Positional struct {
		Files []string `positional-arg-name:"slice definition files"`
	} `positional-args:"yes" required:"true"`
}

func init() {
	parser.AddCommand(
		"install",
		"Install slices",
		"The install command installs all slices from the specified files",
		&cmdInstall{},
	)
}

func (c *cmdInstall) Execute(args []string) error {
	if len(args) > 0 {
		return ErrExtraArgs
	}
	if c.Workers <= 0 {
		return fmt.Errorf("invalid value for --workers: %d", c.Workers)
	}
	if len(c.Positional.Files) == 0 {
		return nil // There is nothing to do.
	}

	var slices []*chisel.Slice
	for _, f := range c.Positional.Files {
		s, err := chisel.ParseSlices(f)
		if err != nil {
			return fmt.Errorf("cannot parse slices from file %s: %w", f, err)
		}
		slices = append(slices, s...)
	}

	// "Ensure" and "Ignore" packages before pruning the slices, because once
	// pruned, some packages may completely be omitted from these checks.
	if c.Ensure || c.Ignore {
		pkgInfo, err := c.queryArchive(slices)
		if err != nil {
			return err
		}
		if c.Ensure {
			if err := ensurePackages(slices, pkgInfo); err != nil {
				return fmt.Errorf("%c Could not ensure packages: %s", cross, err)
			}
		}
		if c.Ignore {
			slices = ignoreMissing(slices, pkgInfo, c.Arch)
		}
	}

	if c.Prune {
		slices = prune(slices)
	}

	g := group(slices, c.Combine)
	return c.install(g)
}

// Group slices for installation. If combine is true, create only one group with
// all slices in it.
func group(slices []*chisel.Slice, combine bool) [][]string {
	var grouped [][]string
	if combine {
		var names []string
		for _, s := range slices {
			names = append(names, s.Name)
		}
		grouped = append(grouped, names)
	} else {
		for _, s := range slices {
			grouped = append(grouped, []string{s.Name})
		}
	}
	return grouped
}

// Prune the list of slices and return only the top-level slices that no slice
// depends on. Installing these slices alone should cover all of the slices.
// It depends on the acyclic dependency policy of chisel slices.
func prune(slices []*chisel.Slice) []*chisel.Slice {
	log.Print("Pruning the list of slices...")

	pending := make(map[string]*chisel.Slice)
	for _, s := range slices {
		pending[s.Name] = s
	}
	for _, s := range slices {
		for _, e := range s.Essential {
			delete(pending, e)
		}
	}
	var todo []*chisel.Slice
	for _, s := range slices {
		if _, ok := pending[s.Name]; ok {
			todo = append(todo, s)
		}
	}
	return todo
}

// Install the groups of slices, concurrently.
func (c *cmdInstall) install(slices [][]string) error {
	if len(slices) == 0 {
		log.Printf("%c Nothing to install :)", tick)
	}
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	tasks := make(chan *task, len(slices)) // Tasks to finish.
	errs := make(chan error, len(slices))  // Errors from the tasks, if any.
	for _, s := range slices {
		tasks <- &task{
			args:   []string{"cut", "--release", c.Release, "--arch", c.Arch},
			slices: s,
		}
	}
	close(tasks)

	done := make(chan bool) // Indicates that the workers are done.
	var wg sync.WaitGroup
	for range min(c.Workers, len(slices)) {
		wg.Add(1)
		go func() {
			defer wg.Done()
			worker(ctx, tasks, errs)
		}()
	}
	go func() {
		wg.Wait()
		// Wait 1 second before sending the done signal as the workers might
		// send an error to the "errs" channel at the same time.
		time.Sleep(1 * time.Second)
		done <- true
	}()

	var allErrs error
loop:
	for {
		select {
		case <-done:
			break loop
		case err := <-errs:
			if err == nil {
				continue
			}
			if !c.Continue {
				cancel()
				return err
			}
			allErrs = errors.Join(allErrs, err)
		}
	}
	return allErrs
}

type task struct {
	args   []string // Chisel arguments without positional slice name(s).
	slices []string // Positional argument - slice name(s) to install.
}

// worker does the actual installation of a list of slices by executing the
// chisel cut command in another process.
// It takes in a context to interrupt when necessary, a stream (channel) of
// tasks and a channel to send errors to.
func worker(ctx context.Context, tasks <-chan *task, errs chan<- error) {
	// We are using an independent cache directory for chisel in each worker.
	// The reason is tricky to detect. When creating files in cache, Chisel
	// temporary saves a file as "<digest>.tmp" in the cache directory.[^1]
	// It later renames the file to "<digest>" within the same directory.[^2]
	// This is OK, if two chisel operations are sequential and/or do not try to
	// "create" the cache at the same time. But on concurrent operations, the
	// second process fails to rename the temporary file and eventually fails.
	//
	//   error: cannot fetch from archive: rename
	//   /home/runner/.cache/chisel/sha256/6b8cc68643d18250ab297c4f6d427a8778b1d1534e1a3033fff0f221fa20a419.tmp
	//   /home/runner/.cache/chisel/sha256/6b8cc68643d18250ab297c4f6d427a8778b1d1534e1a3033fff0f221fa20a419:
	//   no such file or directory
	//
	// [^1]: https://github.com/canonical/chisel/blob/main/internal/cache/cache.go#L112
	// [^2]: https://github.com/canonical/chisel/blob/main/internal/cache/cache.go#L80
	cacheDir, err := os.MkdirTemp("", "")
	if err != nil {
		errs <- fmt.Errorf("cannot create temporary directory: %w", err)
		return
	}

	do := func(task *task) {
		name := strings.Join(task.slices, " ")
		log.Printf("Installing %s...", name)

		dir, err := os.MkdirTemp("", "")
		if err != nil {
			errs <- fmt.Errorf("cannot create temporary directory: %w", err)
			return
		}
		defer os.RemoveAll(dir)

		args := append(task.args, "--root", dir)
		args = append(args, task.slices...)

		cmd := exec.CommandContext(ctx, "chisel", args...)
		cmd.Env = os.Environ()
		cmd.Env = append(cmd.Env, "XDG_CACHE_HOME="+cacheDir)

		if out, err := cmd.CombinedOutput(); err != nil {
			if e, ok := err.(*exec.ExitError); ok && e.ProcessState.ExitCode() != -1 {
				err = fmt.Errorf("%c Failed to install %s: %w", cross, name, err)
				log.Printf("%s\n%s", err, out)
			}
			errs <- err
		} else {
			log.Printf("%c Installed %s", tick, name)
		}
	}

loop:
	for {
		select {
		case <-ctx.Done():
			break loop // Context cancelled. Quit.
		case task, ok := <-tasks:
			if !ok {
				break loop // No more tasks. Quit.
			}
			do(task)
		}
	}
}

// Query the archives for package existence, using the chisel.yaml
// configurations.
func (c *cmdInstall) queryArchive(slices []*chisel.Slice) (map[string]*rmadison.Result, error) {
	p := filepath.Join(c.Release, "chisel.yaml")
	cfg, err := chisel.ParseConfig(p)
	if err != nil {
		return nil, fmt.Errorf("cannot parse chisel.yaml: %w", err)
	}
	ubuntu, ok := cfg.Archives["ubuntu"]
	if !ok {
		return nil, fmt.Errorf("no 'ubuntu' archive in chisel.yaml")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()

	var pkgs []string
	exists := make(map[string]struct{})
	for _, s := range slices {
		if _, ok := exists[s.Package]; !ok {
			pkgs = append(pkgs, s.Package)
			exists[s.Package] = struct{}{}
		}
	}
	res, err := rmadison.QueryWithContext(ctx, &rmadison.QueryOptions{
		Component: ubuntu.Components,
		Suite:     ubuntu.Suites,
		Package:   pkgs,
	})
	if err != nil {
		return nil, fmt.Errorf("cannot query archives: %w", err)
	}
	pkgInfo := make(map[string]*rmadison.Result)
	for _, r := range res {
		pkgInfo[r.Package] = r
	}
	return pkgInfo, nil
}

// Ensure that the slice packages exist for at least one arch.
func ensurePackages(slices []*chisel.Slice, pkgInfo map[string]*rmadison.Result) error {
	log.Println("Ensuring slice packages existence...")
	for _, s := range slices {
		if _, ok := pkgInfo[s.Package]; !ok {
			return fmt.Errorf("package %q does not exist", s.Package)
		}
	}
	return nil
}

// Ignore missing slice packages for a particular arch.
func ignoreMissing(slices []*chisel.Slice, pkgInfo map[string]*rmadison.Result, arch string) []*chisel.Slice {
	log.Printf("Ignoring missing slice packages on %s...", arch)
	var found []*chisel.Slice
	missing := make(map[string]bool)
	for _, s := range slices {
		// Use the missing map to avoid costly [strings.Contains] operation
		// below for all slices of a package.
		if miss, ok := missing[s.Package]; ok {
			if !miss {
				found = append(found, s)
			}
			continue
		}
		info, ok := pkgInfo[s.Package]
		if ok && (strings.Contains(info.Arch, arch) || strings.Contains(info.Arch, "all")) {
			found = append(found, s)
			missing[s.Package] = false
			continue
		}
		log.Printf("... ignored %s for %s", s.Package, arch)
		missing[s.Package] = true
	}
	return found
}
