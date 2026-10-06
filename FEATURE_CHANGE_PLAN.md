# PIG Data Extraction Utility — Change Plan

## Purpose

This document is the working specification for the next set of changes to the PIG Data Extraction Utility. It records the requested features, the parts of the application likely to be affected, dependencies between changes, risks, and details that still need to be agreed upon.

No implementation should begin for an item until its expected behavior and acceptance criteria have been elaborated in this document.

## Scope

The planned work currently covers ten changes:

1. Distinguish `By_Label` extraction output by PIG size and type.
2. Show per-slot extraction progress using a numeric loading indicator.
3. Allow additional operation instances during extraction only.
4. Fix the main progress bar.
5. Fix runs freezing because of particular slots.
6. Overhaul the serial monitor with a VS Code-like experience.
7. Add a slot power-off operation to counter boot-select conditions.
8. Fix UI scrolling, wasted space, and space prioritization.
9. Automatically switch from preferred mode to fallback mode.
10. Fix EGP sensor checking.

## Current Architecture Relevant to These Changes

Most behavior is implemented in `main.py`, including:

- Global run state and cancellation
- Board and slot detection
- Serial communication
- USB/SD-card detection
- File extraction and verification
- Firmware upload, formatting, and labeling
- Sensor checks
- Worker threads and parallel execution
- Main and beginner-mode user interfaces
- Serial monitor
- Progress tracking and run summaries

`boards_config.json` stores board identity and configuration, including board name, type, PIG/pipe size, excluded slots, and total slots.

`custom_file_selection.py` appears to be an older standalone version of the application. Unless a later decision says otherwise, new behavior will be implemented in `main.py` only.

---

## 1. Distinguish `By_Label` Output by PIG Size and Type

### Goal

Organize extracted data under `Extracted_Data/By_Label` so that output can be distinguished using both the configured PIG size and PIG/board type.

### Current behavior

Preferred extraction primarily creates output folders using the detected SD-card label:

```text
Extracted_Data/By_Label/<volume-label>/
```

Board type and `pipe_size` are already available from `boards_config.json`, but are not consistently represented in the destination path.

### Likely modifications

- Define the final directory naming/hierarchy convention.
- Add a single destination-path builder rather than constructing paths inside individual extraction flows.
- Apply the convention to classic, preferred, fallback, and retry extraction flows.
- Define behavior for missing or invalid size/type values.
- Ensure existing extraction folders are not accidentally overwritten.
- Record the resolved type and size in run summaries/logs.

### Areas likely affected

- `BOARD_PIPE_SIZES`
- `BOARD_TYPES_CURRENT`
- `get_board_type()`
- `op_data_slot()`
- `op_data_log_slot()`
- `op_data_pref_slot()`
- `op_data_log_pref_slot()`
- `process_data_pref_pipelined()`
- Extraction retry paths
- Summary/log generation

### Details to elaborate

- Whether existing folders should be migrated

### Agreed behavior

- Directory format: `By_Label/<type>/<size>/<label>/`
- Example: `By_Label/C-MFL/18-inch/CMFLB4S1/`
- Supported type buckets: `A-MFL`, `C-MFL`, and `EGP`
- Positive configured sizes use `<number>-inch`
- Missing, zero, negative, or invalid sizes use `Unknown-size`
- Missing labels use `UNLABELED_B<board-number>S<slot-number>`
- The volume label remains the final directory component
- All directory components are sanitized for Windows paths
- Existing extraction folders are left unchanged; new extractions use the new hierarchy

### Acceptance criteria

- Classic, preferred, log-only, pipelined, and retry extraction paths use one destination builder.
- Identical labels from different PIG types or sizes resolve to different directories.
- Missing size and label values resolve to stable, valid directories.
- Path-building behavior is covered by hardware-independent automated tests.

---

## 2. Per-Slot Numeric Loading Indicator During Extraction

### Goal

Display extraction progress separately for every active slot. The indicator should use a number, expected to be a percentage or another agreed numeric value.

### Scope boundary

This indicator is only for data extraction modes. It should not appear as active progress for formatting, labeling, sensor checking, or firmware uploading.

### Likely modifications

- Extend slot status records with progress fields.
- Report bytes copied and total bytes from the file-copy layer.
- Aggregate multi-file progress into one per-slot value.
- Send thread-safe progress updates to the GUI.
- Render the numeric value in the appropriate slot cell or a dedicated per-slot progress view.
- Define progress behavior during drive detection, verification, retry, failure, and cancellation.

### Areas likely affected

- `StatusTracker`
- `copy_file_with_progress()`
- `copy_sdcard_files()`
- Extraction operation functions
- Qt log/event bridge or a new progress signal bridge
- Progress tables in both beginner and advanced UI

### Details to elaborate

- Whether cancelled extraction should retain its last percentage or use a separate cancelled presentation

### Agreed behavior

- Progress is visible directly in every eligible slot cell in both beginner and advanced progress tables.
- It is not placed behind a setting, secondary option, or separate dialog.
- Active extraction slots use an embedded progress bar with a centered numeric percentage.
- Percentages are calculated from selected top-level file bytes across the whole slot.
- Slots not selected for the current process show `NA`.
- In non-extraction modes, selected slots that are queued show a static hourglass; the hourglass rotates only once that slot is running.
- In extraction modes, selected slots that are queued show a static hourglass; once the slot is reached, it switches to the percentage bar.
- Active copying is capped at `99%` until verification succeeds.
- Successfully copied and verified slots show `100%` in green.
- Failed slots retain their last percentage and show `Failed` in red.
- Percentage text is bold and uses lighter fill colors for readability.
- Active extraction tooltips include byte totals and a live ETA calculated from average copy speed across the whole slot copy workload.
- Failure details are available as tooltips.
- The per-slot bars appear only for `DATA` and `DATA_PREF`; log-only and non-extraction operations retain status symbols.

### Acceptance criteria

- Both progress tables show the same per-slot numeric value.
- Progress is derived from bytes copied, not elapsed time or file count.
- Multiple files contribute to a single slot percentage.
- ETA is based on total selected bytes for the slot, not the current individual file.
- `100%` is not displayed before post-copy verification succeeds.
- Custom-selection runs mark unselected slots as `NA`.
- Switching to a non-extraction operation removes the embedded bars.
- Progress calculation is covered by hardware-independent automated tests.

---

## 3. Additional Instances for More Operations During Extraction

### Goal

Permit an additional isolated app instance to be launched while a process is active, so a different operation can be started without resetting or corrupting the current run state.

### Constraint

The current in-process engine uses single-run globals, so true multi-run execution inside one window is deferred until run state is isolated.

### Likely modifications

- Add a launch control for a separate application process.
- Keep the current process's tracker, mode, cancellation, and progress state isolated from the additional instance.
- Enable the launch control only while a process is active.
- Leave true same-window multi-run scheduling for a later refactor.
- Operator should choose non-overlapping boards, slots, and ports in the additional instance to avoid hardware contention.

### Areas likely affected

- `EngineThread`
- `MainWindow.engine_thread`
- `MODE_CURRENT`
- `RUN_SELECTION`
- `CANCEL_EVENT`
- `BOARD_PORTS_CURRENT`
- Progress and summary globals
- `toggle_controls()` and `toggle_ez_controls()`
- Start, cancel, retry, and completion handlers

### Important risk

The current application uses global state for a single active run. Running multiple operations inside the same process without first isolating per-operation state could mix progress, cancellation, summaries, and hardware ownership. A separate process avoids UI/global-state corruption, but it cannot automatically prevent two app windows from targeting the same physical hardware.

### Implemented behavior

- Advanced mode has a `New Instance` button.
- EZ mode has a `NEW INSTANCE` button.
- File menu has `Open Additional Instance`.
- The controls are enabled only while a run is active in the current window.
- Launch uses the current executable when frozen, or the current `main.py` script when running from source.
- The launched instance has its own `MODE_CURRENT`, tracker, cancel event, and progress UI.

### Remaining hardware ownership notes

- Meaning of “instances”: new windows, background jobs, parallel selections, or multiple application processes
- Operations permitted alongside extraction
- Whether the same board may be used by two operations
- Whether each instance has a separate cancel button and log
- Maximum number of instances
- Expected behavior when two tasks request the same COM port or drive

### Acceptance criteria

- Starting another instance does not stop, reset, or overwrite the current window's active run state.
- The second instance can select a different operation and start normally.
- The current run's progress table and main progress bar continue updating in the original window.
- The implementation does not attempt unsafe in-process reuse of the single global tracker/cancel state.

---

## 4. Fix the Main Progress Bar

### Goal

Make the main progress bar accurately represent the work completed in the current operation.

### Current concerns

- Progress is based on terminal slot states rather than actual extraction work.
- Completion handlers can force the bar to `100%`, including failed or cancelled runs.
- Modes with multiple phases may not be weighted correctly.
- Skipped, excluded, dead, or unprocessed slots can produce misleading totals.
- Concurrent work and retries can make the current global counters inaccurate.

### Likely modifications

- Define progress semantics for every mode.
- Separate successful completion, terminal completion, and work percentage.
- Recalculate totals from the actual selected and eligible slots.
- Ensure each slot is counted only once.
- Handle cancellation and failures without falsely displaying successful completion.
- Coordinate the main bar with the new per-slot extraction progress.

### Areas likely affected

- `PROG_TOTAL_SLOTS`
- `PROG_SLOTS_DONE`
- `_bump_progress_if_terminal()`
- `set_progress_total_from_selected()`
- `refresh_progress()`
- Engine completion and failure handlers
- Retry handlers

### Details to elaborate

- Whether failed terminal slots count toward 100% work completion
- Desired bar state after cancellation
- Whether multi-phase modes use equal phase weights
- Whether the main extraction bar should aggregate byte progress from all slots

### Acceptance criteria

To be defined per mode.

---

## 5. Fix Freeze State Caused by Some Slots

### Goal

Ensure one unresponsive or abnormal slot cannot freeze an entire run or leave the UI permanently busy.

### Likely causes to investigate

- Drive-detection loops waiting for a device or label
- Serial ports disappearing or returning under a different COM number
- Long file-copy or verification operations
- Formatting subprocesses
- Firmware bootloader detection
- Preferred extraction coordinator states that never become terminal
- Worker futures that do not return
- Blocking calls that do not check cancellation

### Likely modifications

- Establish explicit timeouts for every hardware state transition.
- Track per-slot state-transition deadlines.
- Mark timed-out slots as failed and continue with remaining slots.
- Ensure all coordinator states can reach a terminal condition.
- Improve cancellation checks inside long-running operations.
- Add diagnostic logs containing board, slot, current phase, and elapsed time.
- Ensure worker-thread exceptions always update slot state.

### Areas likely affected

- Serial communication helpers
- Drive detection helpers
- File copy and verification
- Formatting helpers
- Firmware upload helpers
- `process_data_pref_pipelined()`
- Thread-pool loops and QThread completion handling

### Details to elaborate

- Known board/slot combinations that reproduce the freeze
- Last visible status and log line during a freeze
- Maximum acceptable wait for serial, SD mounting, copying, formatting, and bootloader transitions
- Whether a timed-out slot should be retried automatically

### Acceptance criteria

- A failed slot must not prevent other selected slots from completing.
- Every started slot must eventually reach success, failure, skipped, or cancelled state.
- The GUI must regain control after the run reaches a terminal state.
- Additional criteria to be defined from reproduction cases.

---

## 6. Serial Monitor Overhaul — VS Code-Like Experience

### Goal

Replace the current basic serial monitor with a more capable interface inspired by VS Code’s terminal/serial workflow.

### Possible feature areas

- Tabbed serial sessions
- Multiple ports open at the same time
- Clear connection state per tab
- Port and baud-rate selectors
- Connect, disconnect, reconnect, and auto-reconnect
- Timestamp toggle
- Auto-scroll toggle
- Clear and save output
- Search/filter output
- Line-ending selection
- Command history
- Resizable terminal-focused layout
- Dark terminal styling and readable monospace text
- Non-blocking high-volume serial reading

### Likely modifications

- Redesign `SerialMonitorWindow`.
- Review `SerialReaderThread` buffering, shutdown, and error handling.
- Integrate or replace portions of `AdvancedDialog` serial handling.
- Add session-level connection state instead of relying on one monitor reference.
- Protect ports currently owned by extraction or other operations.

### Areas likely affected

- `SerialReaderThread`
- `SerialMonitorWindow`
- `AdvancedDialog`
- Main-window menus and actions
- Serial-port ownership introduced by change 3

### Details to elaborate

- Required VS Code behaviors versus visual inspiration only
- Required number of simultaneous serial sessions
- Default baud rate and supported alternatives
- Required line endings
- Whether ANSI colors/control sequences should be supported
- Whether monitor sessions may connect to ports used by an active operation
- Whether logs should be saved automatically

### Acceptance criteria

To be defined after the desired monitor feature set is prioritized.

---

## 7. Slot Power-Off Feature to Counter Boot-Select

### Goal

Provide a controlled way to power off a slot when it is stuck or left in a boot-select/bootloader condition.

### Implemented behavior

- Added mode `17. POWER OFF ALL SLOTS`.
- Added EZ button `POWER OFF ALL SLOTS`.
- The operation enters slot management by sending command `1`.
- It sends the slot power-off commands with 0.5s gaps:
  - Slot 1: `26`
  - Slot 2: `27`
  - Slot 3: `28`
  - Slot 4: `29`
  - Slot 5: `30`
  - Slot 6: `31`
  - Slot 7: `32`
  - Slot 8: `40`
- The operation logs each command and marks each slot's `power_off` phase as success or failed.
- Custom selection can limit which slot power-off commands are sent; otherwise all mapped commands are sent.
- Board slot limits are respected; 5-slot boards only send slot 1-5 commands (`26` through `30`).
- Boot/upload flows now power off the target slot before sending the slot boot command. Example: booting slot 1 sends `26`, waits 0.5s, then sends `1`.
- The pre-boot power-off logic is shared by DATA boot, format boot, classic label boot, MFL/CMFL/EGP burn, auto burn, retry boot, and sensor recovery burn paths.

### Likely modifications

- Add a slot power-off hardware command or command sequence.
- Expose power-off for a selected board and slot.
- Optionally invoke it automatically during recovery paths.
- Confirm that the command is sent only to the intended board/slot.
- Update slot state and logs after the action.
- Define whether and when power should be restored.

### Areas likely affected

- Serial command helpers
- Slot-level operation functions
- Firmware upload and recovery paths
- Retry and timeout recovery
- Beginner/advanced UI controls
- Serial monitor command ownership

### Safety considerations

- Power control must not interrupt copying or formatting on the same slot.
- The exact firmware menu state and command sequence must be confirmed.
- Automatic power-off requires strict timeout and ownership rules.

### Details to elaborate

- Exact serial command sequence for slot power off
- Supported board types and firmware versions
- Manual only versus automatic recovery
- Required confirmation dialog
- Whether power-on is another explicit feature
- Expected delay before another operation may use the slot

### Acceptance criteria

- Starting `POWER OFF ALL SLOTS` enters slot management with `1`.
- The mapped commands are sent in slot order with 0.5s gaps.
- Serial failures are logged per slot.
- Normal progress/status UI updates for the operation.
- Boot-required operations send the mapped power-off command before the slot boot command.

---

## 8. UI Layout, Scrolling, and Space Prioritization

### Goal

Fix scrolling problems, reduce wasted space, and give the most important controls and status information priority.

### Likely modifications

- Audit beginner page, advanced page, registry dialog, scope dialog, serial monitor, and list/about dialogs.
- Add scroll areas only where content can exceed the window.
- Correct layouts that use excessive fixed spacing or minimum sizes.
- Improve splitter behavior and stretch factors.
- Prioritize board/slot status, current operation, progress, and failures.
- Reduce space used by secondary configuration while a run is active.
- Verify behavior at smaller display sizes and Windows display scaling.
- Preserve accessibility and usable click targets.

### Areas likely affected

- `MainWindow.__init__()`
- `_build_ez_page()`
- `ScopeDialog`
- `RegistryDialog`
- `SerialMonitorWindow`
- `AdvancedDialog`
- Qt layouts, splitters, table policies, and size policies

### Details to elaborate

- Target minimum resolution
- Windows scaling levels that must work
- Screens/dialogs currently failing to scroll
- Sections considered highest priority
- Whether beginner and advanced pages should be reorganized
- Whether a UI mockup is required before implementation

### Acceptance criteria

To be defined screen by screen.

---

## 9. Automatic Preferred-to-Fallback Switching

### Goal

When a preferred workflow cannot complete, automatically attempt its corresponding fallback workflow without requiring the user to restart the operation manually.

### Expected mapping to confirm

Potential mappings include:

| Preferred mode | Possible fallback |
|---|---|
| `DATA_PREF` | `DATA` |
| `DATA_LOG_PREF` | `DATA_LOG` |
| `MFL_PREF` | `MFL` |
| `LABEL_PREF` | `LABEL` |

### Likely modifications

- Define failures that trigger fallback.
- Preserve board and slot selection during the switch.
- Reset the board/menu/slot safely before starting fallback.
- Avoid duplicating files that were already copied successfully.
- Record both preferred and fallback attempts in slot status.
- Ensure progress and summaries report the final outcome accurately.
- Prevent endless switching or repeated retries.

### Areas likely affected

- Preferred slot operations
- Preferred board processors
- `process_data_pref_pipelined()`
- Classic/fallback operations
- `StatusTracker`
- Retry logic
- Summary and simple-log output

### Details to elaborate

- Exact preferred modes that require fallback
- Failure conditions that should trigger fallback
- Whether fallback occurs per slot or for the entire board
- Maximum fallback attempts
- Whether the user can disable automatic fallback
- How partial files are handled before fallback
- Required UI indication that fallback is active

### Acceptance criteria

To be defined for each preferred/fallback pair.

---

## 10. Fix EGP Sensor Check

### Goal

Correct the EGP sensor-check workflow so that it reliably selects slots, reads the expected sensor output, evaluates it correctly, and recovers hardware state afterward.

### Current relevant behavior

- EGP boards are filtered separately from MFL/CMFL boards.
- The application selects slots through serial commands.
- Sensor output is parsed using TMAG angle-related expressions.
- Sensor firmware recovery and slot cleanup are part of the flow.

### Likely modifications

- Capture a reproducible failing EGP output sample.
- Verify the correct slot/menu command sequence.
- Correct parsing for the actual EGP firmware output format.
- Define expected sensor IDs and valid values.
- Distinguish missing output, malformed output, invalid values, and port loss.
- Review bootloader/serial re-enumeration handling.
- Guarantee slot power-off or disconnect cleanup after the check.
- Include useful per-sensor details in logs and summaries.

### Areas likely affected

- `parse_tmag_angle_values()`
- `monitor_tmag_angle_values()`
- `op_sensor_check_egp_slot()`
- `process_board_sensor_check_egp()`
- Sensor recovery helpers
- Slot power-off work from change 7
- Sensor status presentation

### Details to elaborate

- Current failure symptom
- Raw EGP serial output from a working and failing device
- Expected number of sensors
- Valid angle/value ranges
- Required sample duration
- Firmware/menu commands used by the current EGP version
- Expected cleanup and firmware restoration behavior

### Acceptance criteria

To be defined using real EGP test cases and captured output.

---

## Cross-Cutting Design Work

Several requests depend on the same underlying improvements.

### Per-operation state

Changes 2, 3, 4, 5, and 9 will be safer if global run data is grouped into a per-operation context containing:

- Operation identifier
- Mode
- Board and slot selection
- Cancellation event
- Status tracker
- Progress totals
- Start and finish timestamps
- Hardware ownership
- Log and summary destinations

### Hardware ownership

Changes 3, 6, 7, and 9 require a central mechanism that prevents two tasks from controlling the same COM port, board, slot, or removable drive simultaneously.

### Explicit slot state machine

Changes 2, 4, 5, 7, 9, and 10 would benefit from explicit states such as:

```text
queued
selecting_slot
waiting_for_drive
copying
verifying
preferred_failed
fallback_running
recovering
success
failed
timed_out
cancelled
```

### Timeouts and recovery

All hardware waits should have a documented timeout, terminal status, cleanup action, and optional retry/fallback policy.

## Proposed Implementation Order

The order below minimizes conflicts between features:

1. Reproduce and document slot freezes and EGP sensor failures.
2. Introduce per-operation state and hardware ownership boundaries.
3. Fix terminal slot states, timeouts, cancellation, and the main progress model.
4. Add per-slot numeric extraction progress.
5. Add preferred-to-fallback transitions.
6. Add slot power-off and integrate it into recovery paths.
7. Add controlled additional operations during extraction.
8. Apply PIG type/size output organization.
9. Overhaul the serial monitor.
10. Complete the responsive layout and space-prioritization pass.

This order can be changed after requirements are elaborated.

## Testing Strategy

### Unit-level tests

- Label parsing and destination-path generation
- PIG type/size normalization
- Sensor-output parsing
- Progress aggregation
- State transitions and timeout handling
- Preferred-to-fallback decision rules

### Simulated integration tests

- Fake serial ports and scripted responses
- Simulated port disappearance/reappearance
- Simulated removable-drive mounting and timeout
- Copy success, partial copy, retry, verification failure, and cancellation
- Multiple operations requesting the same hardware

### Hardware validation

- A-MFL with five-slot configuration
- C-MFL with eight-slot configuration
- EGP boards
- Excluded slots
- Missing/unlabeled SD cards
- Preferred extraction success and fallback
- Boot-select recovery and slot power-off
- Sensor-check success, missing sensor, malformed output, and port loss

### UI validation

- Small supported resolution
- Common Windows display-scaling settings
- Long board names and many connected boards
- Multiple serial-monitor sessions
- Active extraction plus allowed secondary operation
- Cancellation, failure, fallback, and retry presentation

## Documentation and Packaging Updates

Implementation may also require updates to:

- `README.md`
- `README_BUILD_EXE.txt`
- `build_exe.py`
- `PIG_DATA_EXTRACTION_UTILITY.spec`
- Configuration schema/version in `boards_config.json`
- A dependency file, if new libraries are introduced

## Decisions Log

Use this section to record agreed behavior before implementation.

| Date | Change | Decision | Reason |
|---|---|---|---|
| 2026-10-05 | 1 | Use `By_Label/<type>/<size>/<label>` and preserve existing output | Prevent collisions while retaining label-first traceability within each PIG configuration |
| 2026-10-05 | Testing | Use standard-library unit tests for pure logic | Tests run offline without requiring PyQt, serial hardware, or additional packages |
| 2026-10-05 | 2 | Show byte-based numeric bars directly in slot cells for `DATA` and `DATA_PREF` | Keeps concurrent slot progress continuously visible without adding another option or window |

## Implementation Status

| # | Change | Requirements | Design | Implementation | Hardware validation |
|---:|---|---|---|---|---|
| 1 | Type/size-based `By_Label` output | Defined | Complete | Complete | Pending |
| 2 | Per-slot extraction progress | Defined | Complete | Complete | Pending |
| 3 | Additional extraction-time instances | Draft | Not started | Not started | Not started |
| 4 | Main progress bar | Draft | Not started | Not started | Not started |
| 5 | Slot freeze-state fix | Draft | Not started | Not started | Not started |
| 6 | VS Code-like serial monitor | Draft | Not started | Not started | Not started |
| 7 | Slot power off | Draft | Not started | Not started | Not started |
| 8 | UI scrolling and space fixes | Draft | Not started | Not started | Not started |
| 9 | Preferred-to-fallback switching | Draft | Not started | Not started | Not started |
| 10 | EGP sensor-check fix | Draft | Not started | Not started | Not started |
