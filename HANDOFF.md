# Express Report Extraction — Handoff / Cold-Start File

**Purpose:** add a feature to the extraction utility (`Kinben-Electronics-Team/iPIG_HMI_AUTOMATION`) that works like the existing "log summary" (DATA_LOG mode). It pulls **1 packet per MB** from every hub slot, plus the INLB and ODO data, into a small folder. The site engineer uploads that folder and the office builds the **Express Report** from it.
Reference report: `C:\Users\manas\Claude\Projects\Utility\16 Inch CAIRN Suvali to NTPC Kawas_EGP_ER_Rev.0.docx`.
Sections in that report: Operating conditions, System diagnostics (sensor counts before/after the run), Recorded line length, Temperature plot, Velocity plot, Conclusion (dents/ovality).
**Status (2026-10-13):** estimates done, and one 12" EGP static capture analysed. **No code written yet.** Nothing is running.

## Folder map
```
Express Report Extraction/
├── HANDOFF.md        ← this file
└── scripts/          ← analysis scripts used on the 12" EGP capture (python -I, numpy)
    ├── frames.py     ← sync/frame alignment check per hub file
    ├── chan3.py      ← per-EGP-sensor health (angle deg + 3 TMAG X/Y), firmware-correct decode
    └── spk.py        ← time-binned arm deflection + counter-gap timing
```
Repos referenced (shallow clones lived in the session scratchpad; re-clone with `gh repo clone Kinben-Electronics-Team/<name>`):
- `iPIG_HMI_AUTOMATION`: the utility. All logic is in `main.py` (5.4k lines). Change plan: `FEATURE_CHANGE_PLAN.md`.
- `HUB-Code-Combined-Board-V2.0`: slot/master firmware. EGP frame = `include/function.h` (SAMPLE_BUFFER_SIZE 112). Packing = `lib/MFLSensorHead/LDC1101.cpp` `getEGPdata()`, angle decode `liveReadAngle()`.
- `INAV-Code-Inertial-Navigation-Board-V1.0`: INLB firmware. 98 B record format documented at the top of `src/main.cpp`.

## How the utility extracts today (verified from main.py, 2026-10-12)
- **Fallback ("DATA EXTRACTION FALLBACK", mode DATA):** per slot: power-off check → slot cmd → 2 s → bootloader drive → copy `DATA.uf2` → **5 s sleep** → wait for SD to enumerate as USB MSC by volume label (30 s timeout, then a 30 s new-drive fallback) → copy → `disconnect_mux`. The RP2040 serves the SD card over **USB Full-Speed (~1 MB/s)**. A global `BOOT_LOCK` serialises the boot and enumerate steps across all boards. Slots within a board run one after another.
- **Preferred (DATA_PREF):** the hub's USB2642 reader. Cards are switched in one at a time, USB 2.0, about 20 MB/s.
- **DATA_LOG** = `log_sdcard_file_info()`: writes `data_log.txt` (file names and sizes only). The new feature should plug in at the same place (`op_data_log_slot` / `op_data_log_pref_slot`).
- ODO/INLB = `process_odo_extraction()` / `process_inlb_extraction()`, serial command sequences with 2 s gaps.

## Sizing model (Manas's definition: worst case = bottlenecked by RP2040 native USB)
Inputs: 2 sensors/inch, 1 sensor per slot, 8 slots per hub. MFL frame 64 B at a 2 kHz cap gives ≤0.46 GB per run-hour per card. 1 packet/MB is about 461 packets per slot per run-hour.
Per-slot fixed overhead: ~25 s nominal, **~60 s worst case** (boot/enumerate).

| | Per-packet cost | Time formula |
|---|---|---|
| **A** naive (Windows cached read pulls a 32–64 KB cluster) | ~100 ms | inches × (2 + 1.5 × run-h) min + 5 min |
| **B** spec'd (raw/unbuffered 512 B sector read per sample) | ~5 ms | inches × (2 + 0.08 × run-h) min + 5 min |
| Full copy over the same path (reference) | — | ~15 min per inch per run-hour |

Size ≈ 0.25 MB × inches × run-h + 5 MB (CSV worst case; binary is about 4× smaller; zip is about 3×).

| Tool | 10 h (A / B / size) | 24 h | 48 h |
|---|---|---|---|
| 10" | ~3 h / ~35 min / ~30 MB | ~6.5 h / ~45 min / ~65 MB | ~12.5 h / ~1 h / ~125 MB |
| 24" | ~7 h / ~1.2 h / ~65 MB | ~15 h / ~1.6 h / ~150 MB | ~30 h / ~2.4 h / ~290 MB |
| 42" | ~12 h / ~2 h / ~110 MB | ~27 h / ~2.8 h / ~260 MB | ~52 h / ~4 h / ~510 MB |

**Key spec point:** the implementation MUST be option B (unbuffered sector reads, or raw volume reads at offsets from the file's cluster map). Option A isn't workable for big tools or long runs.
Caveats: these are upper bounds (2 kHz all run long; 48 h × 0.46 GB = 22 GB, which is more than a 16 GB card holds). Per-packet costs are estimates and **untimed on hardware**: time one 8-slot hub to calibrate. The sampled set supports the diagnostics, line length, temperature and velocity sections, **not** the dent/defect conclusions (1 sample per ~9–15 m of pipe).

## EGP go/no-go from arm angle + arm length (EGP runs at 1 kHz → 112 B × 1 kHz = ~0.4 GB per run-hour per card)
- Sampling can't do this: a dent lasts about 60–150 ms, and 1 packet per MB is 1 frame every ~9 s.
- PC-side full read over the RP2040 USB: ~7–8.5 min per slot per run-hour, serial. 10"/10 h ≈ 28 h. **Not viable.**
- **Recommended: on-hub scan.** A new firmware mode (scan command or SCAN.uf2). Each slot RP2040 reads its own SD over 4-bit SDIO (~5–10 MB/s, estimated), computes deflection = L·sin θ from the zero reference, keeps the peak per metre or per second, flags exceedances, and writes a summary of ~30 KB per slot per run-hour. All slots scan in parallel.
  Time ≈ inches × 3 min + 1.35 min × run-h + 5 min (worst case). Examples: 10"/10 h ~50 min; 42"/48 h ~3.3 h. If the verdict returns over the master serial link (no per-slot boot), the total is about 10–70 min for any tool size. **Unverified** whether the hub serial/I2C link can carry this.
- Needed from Manas: arm length and zero reference per size, thresholds (dent 2%/6% OD, ovality), and confirmation that "angle sensors" = arm TMAG angle (assumed), not the INLB bend/IMU.

## Data formats (decoded 2026-10-12, firmware-verified unless marked)
- **Hub EGP frame 112 B:** [0..15] sync `f1e2d3c4b5a69788796a5b4c3d2e1f10`. Then **5 EGP sensors × 14 B** from offset 16: 2 B angle (BE; **deg = (raw & 0x1FFF)/16**) + 3 × 4 B TMAG5170 32-bit special read. [86..88] 24-bit LE sample counter. Zero pad to 112.
  TMAG word bytes B1..B4: **X = s12(((B2&0xF)<<8)|(B3&0xF0)|(B4>>4))**, **Y = s12(((B1&0xF)<<8)|(B2&0xF0)|(B3&0xF))**. Status nibble = B1>>4 (2 = normal).
  The number of EGPs per slot is configurable (`UPDATE_NUM_EGP`); this tool has 5.
- **ODO frame 32 B:** sync (11 B incl. 0x5B), [11..13] 24-bit LE counter, 3 × 4 B channel words at 20/24/28 (decode not verified; treated as live/not-live only).
- **INLB record 98 B:** [0..9] sync, [10..16] RTC BCD (sec, min, hour, weekday, date, month, year), [17..24] temps: TMP461 0x4E remote hi/lo, local hi/lo, then 0x48 the same. **ASSUMED: the hi byte = whole °C.** The lo byte reads 0xFF (the register pointer doesn't auto-increment). [25] ODO status, [26..33] CSB sample count (u64 LE), [34..97] HG4930 IMU (20 B control msg + 44 B inertial msg).

## 12" EGP static capture check (`C:\Users\manas\Downloads\Extracted_Data\Extracted_Data`, ~9 min at 1 kHz)
Contents: 1 hub (EGPB1 S1–S4, 61.4 MB each = 548,474 frames), INLB (3 files, 545,832 records), ODO (548,484 records).
**Hub: all 20 angle + 60 TMAG sensors online** (no stuck, rail or zero readings; status normal; TMAGs read about 0 mT at rest).
Handling/deflection event at ~420–480 s:
- Moved and returned to rest: S1 E2–E5, S2 E1–E5, S3 E1, E2.
- **S3.E3 (+4.3°) and S3.E4 (+6.8°) didn't return to rest** (S3.E1 +1.7°). Check the spring/hinge.
- **S1.E3: intermittent zero dropouts**, 1.2% of samples (~6.6k isolated dropouts). Check the cable/connector.
- **7 bottom arms the tech couldn't move** (S1.E1, S3.E5, S4.E1–E5): all live, reading 197–268° with 0.2–0.6° noise. Six of them stepped ~1–1.6° when the tool was handled (loaded, so responsive). S1.E1 and S4.E5 barely moved (0.2–0.3°). Re-test with the tool lifted.
**INLB:**
- ❌ **HG4930 IMU bytes all zero in 100% of records** (no IMU/bend data).
- ❌ **RTC never set** (reads 2000-01-05). Fix with INLB command 13.
- Temperatures: 3 of 4 channels OK (51→59 °C, warming). 0x4E remote reads constant −64 °C (probe open/disconnected).
- CSB sample count absent for the first ~229 s, then only ~185 updates.
**ODO:** live, continuous counter, 3 channels noisy around a constant. Wheels not turned, so pulses are unverified.
**Data handling:**
- (1) S1 file's first 5 frames overwritten by the Windows indexer's `IndexerVolumeGuid`. **Disable removable-drive indexing on the extraction laptop.**
- (2) Every slot writes `HID01SID03_*` (slot IDs not configured), so copying the files into one folder would overwrite them.
- (3) Hub counter skips ~3.5% of counts (1%→6% over the run). Yet all devices logged the same number of records, so the counter source needs looking at.
**Verdict given: NO-GO** until the IMU, RTC, the 7 unproven arms, S1.E3 and S3.E3/E4 are fixed. Open: is 20 EGP arms (1 hub × 4 slots) the correct count for this 12" tool?

## Open questions for Manas
1. CSM V4.3 MFL frame size and real trigger mode (distance- or time-based). This sets the real data volume.
2. CSV vs binary for the sampled output; packet = 1 frame or a small burst per MB?
3. Approve option B (raw sector reads) as a hard requirement in `FEATURE_CHANGE_PLAN.md`?
4. On-hub EGP scan: firmware owner? Scan as a command in the logging firmware vs a separate UF2?
5. EGP thresholds plus arm length/zero per tool size (see above).
6. Expected EGP arm count for the 12" tool.

## ⏩ NEXT SESSION BOOTSTRAP
1. Read this file. Get answers to the open questions (batched, ask once).
2. Re-clone `iPIG_HMI_AUTOMATION`. Write the feature spec as a new item in `FEATURE_CHANGE_PLAN.md` (sampled extraction: output layout, binary format, sector-read method, ODO/INLB decimation, timing targets).
3. Bench-calibrate: time one fallback slot (boot overhead + 461 sampled reads, cached vs unbuffered) and update the formulas.
4. If the EGP go/no-go is approved: spec the scan mode against `HUB-Code-Combined-Board-V2.0`.
