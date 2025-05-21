package main

import (
	"fmt"
	"log"
	"os"

	"github.com/jessevdk/go-flags"
)

// ErrExtraArgs is returned  if extra arguments to a command are found
var ErrExtraArgs = fmt.Errorf("too many arguments for command")

var parser = flags.NewParser(&struct{}{}, flags.Default)

func main() {
	// We do not care for any date/time prefix on the logs.
	log.SetFlags(0)

	if _, err := parser.Parse(); err != nil {
		switch flagsErr := err.(type) {
		case flags.ErrorType:
			if flagsErr == flags.ErrHelp {
				os.Exit(0)
			}
			os.Exit(1)
		default:
			os.Exit(1)
		}
	}
}
