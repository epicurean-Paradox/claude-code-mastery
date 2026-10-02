"""Coverage-guided driver (Atheris) over fuzz/targets.py.

Usage (Linux; libFuzzer flags pass through):
    python3 fuzz/fuzz.py <regions|ledger|evidence> <work-corpus-dir> fuzz/corpus/<target> \\
        -max_total_time=40 -timeout=10 -max_len=16384 -artifact_prefix=fuzz-out/<target>-

The first corpus directory is where libFuzzer writes new inputs; keep it outside the committed
corpus. Reproduce a crash with `python3 fuzz/fuzz.py <target> <crash-file>`.
"""

import sys

import atheris

import targets

if len(sys.argv) < 2 or sys.argv[1] not in targets.TARGETS:
    sys.exit(f"usage: fuzz.py <{'|'.join(targets.TARGETS)}> [libFuzzer args]")
TARGET = targets.TARGETS[sys.argv.pop(1)]


def test_one_input(data):
    TARGET(data)


def main():
    # The parsers are loaded by file path, which instrument_imports() does not see.
    atheris.instrument_all()
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
