# YAML Checker

An internal CLI util for formatting and validating YAML files. This project
relies on Pydantic and Ruamel libraries.

**Installation**
```bash
pip install -e yaml_checker
```

**Usage**
```
usage: yaml_checker [-h] [-v] [-w] [--config CONFIG] [files ...]

positional arguments:
  files            Additional files to process (optional).

options:
  -h, --help       show this help message and exit
  -v, --verbose    Enable verbose output.
  -w, --write      Write yaml output to disk.
  --config CONFIG  CheckYAML subclass to load
```

**Example**

```bash
# Lets cat a demonstration file for comparison. 
$ cat yaml_checker/demo/slice.yaml
# yaml_checker --config=Chisel demo/slice.yaml

package: grep

essential:
    - grep_copyright

# hello: world

slices:
  bins:
    essential:
    - libpcre2-8-0_libs # tests

    # another test
    - libc6_libs
    contents:
              /usr/bin/grep:

  deprecated:
    # These are shell scripts requiring a symlink from /usr/bin/dash to
    # /usr/bin/sh.
    # See: https://manpages.ubuntu.com/manpages/noble/en/man1/grep.1.html
    essential: 
    - dash_bins
    - grep_bins
    contents:
      # we ned this leading comment
      /usr/bin/rgrep: # this should be last

      /usr/bin/fgrep:

      # careful with this path ...
      /usr/bin/egrep: # it is my favorite 
  copyright:
      contents:
          /usr/share/doc/grep/copyright:
# Note: Missing new line at EOF

# Now we can run the yaml_checker to format the same file.
# Note how comments are preserved during sorting of lists and
# dict type objects. If you want to test the validator, 
# uncomment the hello field. 
$ yaml_checker --config=Chisel yaml_checker/demo/slice.yaml
# yaml_checker --config=Chisel demo/slice.yaml

package: grep

essential:
  - grep_copyright

# hello: world

slices:
  bins:
    essential:
      - libc6_libs
      - libpcre2-8-0_libs # tests

    # another test
    contents:
      /usr/bin/grep:

  deprecated:
    # These are shell scripts requiring a symlink from /usr/bin/dash to
    # /usr/bin/sh.
    # See: https://manpages.ubuntu.com/manpages/noble/en/man1/grep.1.html
    essential:
      - dash_bins
      - grep_bins
    contents:
      # we ned this leading comment

      #  careful with this path ...
      /usr/bin/egrep:  #  it is my favorite
      /usr/bin/fgrep:
      /usr/bin/rgrep: #  this should be last
  copyright:
    contents:
      /usr/share/doc/grep/copyright:

```
