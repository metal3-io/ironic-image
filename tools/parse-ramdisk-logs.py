#!/usr/bin/env python3

import argparse
import os
import re
import sys

# extraction datetime is always irrelevant
EXTRACTION_TS = re.compile(r"^[0-9TZ\.:\-]* ?")
CONTENTS = re.compile(r"\*{12} Contents of (?P<path>/.*)\.tar\.gz ")
ENTRY = re.compile(r"\*{4} Entry: (?P<entry>.*) \*{4}")


def log(msg):
    print(msg, file=sys.stderr)


class VisitorEntry:
    """Visitor for one entry - one file in the output."""

    def __init__(self, dest: str, entry_name: str):
        assert entry_name is not None
        path = os.path.join(dest, entry_name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.file = open(path, "w", encoding="utf-8")

    def close(self):
        self.file.close()

    def __call__(self, line: str):
        self.file.write(f"{line}\n")


class VisitorSingleRun:
    """Visitor for a single run - inspection, cleaning or deploy."""

    def __init__(self, dest: str, filename: str):
        assert filename is not None
        self.filename = os.path.basename(filename)
        self.delim = f"{self.filename}.tar.gz:"

        log(f"Processing {self.filename}")
        # Possible formats (path and .tar.gz suffix already stripped):
        # UUID_NAMESPACE~NAME_inspect_TS
        # UUID_NAMESPACE~NAME_INSTUUID_cleaning_TS
        # UUID_NAMESPACE~NAME_INSTUUID_TS
        _, name, *_, stage, ts = self.filename.split("_")
        if stage not in ("cleaning", "inspect"):
            stage = "deploy"
        log(f".. {stage} on node {name} at {ts}")

        self.dest = os.path.join(dest, name, f"{stage}-{ts}")

        # Visitor for the current entry (file from the ramdisk)
        self.visitor: VisitorEntry = None

    def close(self):
        if self.visitor is not None:
            self.visitor.close()

    def __call__(self, line: str):
        try:
            line = line.split(self.delim, 1)[1]
        except IndexError:
            pass
        else:
            # Strip exactly one space from the start, if any
            if line[0:1] == " ":
                line = line[1:]

        entry = ENTRY.match(line)
        if entry is not None:
            if self.visitor is not None:
                self.visitor.close()
            self.visitor = VisitorEntry(self.dest, entry.group("entry"))
        elif self.visitor is None:
            log(f".. skipping line without a file: {line}")
        else:
            self.visitor(line)


def parse(source: str, dest: str):
    """Parse the log file at source and unpack all entries at dest."""
    # Visitor is an object that is currently responsible for handling new
    # lines.  These objects are hierarchical: top level is host (Ironic node),
    # second level is specific source (file or command). Initially, visitor is
    # None: such lines are skipped.
    visitor: VisitorSingleRun | None = None

    # Skipped is the counter for initially skipped lines.Unfortunately, this
    # may include not just the inotify chatter but also useful lines if the
    # logs have been rotated. There is nothing that can be done here: the file
    # name is only available in the beginning of a dump.
    skipped = 0

    with open(source, "r", encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()

            if "pyinotify DEBUG" in line:
                continue

            line = EXTRACTION_TS.sub("", line, count=1)

            contents = CONTENTS.match(line)
            if contents is not None:
                if visitor is None:
                    if skipped > 0:
                        log(f"Skipped {skipped} lines because they don't have "
                            "any context")
                    skipped = 0
                else:
                    visitor.close()
                visitor = VisitorSingleRun(dest, contents.group("path"))
                continue

            if visitor is None:
                skipped += 1
                continue

            visitor(line)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", help="source file")
    parser.add_argument("destination", help="destination directory")
    args = parser.parse_args()
    parse(args.source, args.destination)


if __name__ == '__main__':
    sys.exit(main())
