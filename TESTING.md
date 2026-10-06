# Development Test Environment

The automated tests are isolated from physical PIG boards, serial ports, and
removable drives. Pure application logic should be moved into small modules
such as `extraction_paths.py` and tested there before it is connected to the
hardware workflow in `main.py`. Byte-to-percentage and ETA rules are isolated
in `extraction_progress.py` so the UI and copy engine share the same behavior.

## Run the tests

From the repository root:

```powershell
python -m unittest discover -s tests -v
```

The current suite uses only Python's standard library. No package installation
or network access is required.

If pytest is installed, the same suite can also be run with:

```powershell
python -m pytest
```

## Syntax check

```powershell
python -m py_compile main.py extraction_paths.py extraction_progress.py
```

## Test boundaries

Automated tests must not:

- Send commands to real serial ports
- Format, label, mount, or unmount real drives
- Upload firmware
- Write into production `Extracted_Data` folders

Hardware integration tests will be documented separately and must be run only
with an explicitly selected test board and slot.

## Baseline

`main_baseline.py` is the byte-for-byte snapshot of `main.py` taken before this
feature implementation began. It is a reference copy, not the development
entry point. All new work belongs in `main.py` and the extracted support/test
modules.
