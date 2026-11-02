# Software and Data Science Team Handoff: Express Report Sampling

## Quick explanation

The log-summary and Express features are separate menu options:

```text
12. DATA EXTRACTION LOG
18. EXPRESS REPORT EXTRACTION
```

Option 12 creates only the original filename-and-size log summary. Option 18 creates both that log summary and a small sampled overview of each original SD-card file. It does **not** copy the entire file.

For **AMFL and CMFL**, the utility keeps:

```text
1 packet out of every 16,384 packets
```

Each AMFL/CMFL packet is 64 bytes, so 16,384 packets occupy exactly 1 MiB:

```text
16,384 packets x 64 bytes = 1,048,576 bytes = 1 MiB
```

In other words, the utility takes one 64-byte packet at the start of every 1 MiB section of the source file.

## Simple AMFL/CMFL example

Using human-friendly packet numbers, the utility samples:

| Sample | Packet kept | Position in the source file |
| ---: | ---: | ---: |
| 1 | 1 | 0 MiB |
| 2 | 16,385 | 1 MiB |
| 3 | 32,769 | 2 MiB |
| 4 | 49,153 | 3 MiB |

This pattern continues until the end of the file.

```text
Original AMFL/CMFL file

| packet 1 | ... 16,383 packets ... | packet 16,385 | ... | packet 32,769 |
     KEEP                                  KEEP                  KEEP
     0 MiB                                 1 MiB                 2 MiB
```

The sampling rate is approximately **0.0061% of the source packets**.

## What happens at the end of a file?

The utility takes one sample from every started 1 MiB section, including the last section when it is smaller than 1 MiB.

Examples for AMFL/CMFL:

| Source file size | Samples created |
| --- | ---: |
| Less than one complete 64-byte packet | 0 |
| 64 bytes through 1 MiB | 1 |
| More than 1 MiB through 2 MiB | 2 |
| More than 2 MiB through 3 MiB | 3 |

Only complete 64-byte packets are written to the Express output.

## Packet sizes by sensor type

| Sensor type | Packet size | Sampling method |
| --- | ---: | --- |
| AMFL | 64 bytes | 1 packet per 16,384 packets (1 per MiB) |
| CMFL | 64 bytes | 1 packet per 16,384 packets (1 per MiB) |
| EGP | 112 bytes | 1 packet per MiB, aligned to a 112-byte packet |

For EGP, 1 MiB is not evenly divisible by 112 bytes. The utility therefore moves slightly backward from each 1 MiB mark to the beginning of a complete EGP packet.

## What the utility reads from the SD card

Windows reads the SD card in 512-byte sectors. For each sample, the utility:

1. Reads the 512-byte sector or sectors containing the required packet.
2. Keeps only the required 64-byte AMFL/CMFL packet or 112-byte EGP packet.
3. Discards the other bytes read from the sector.

The extra sector bytes are **not** saved in the Express file.

## Folders and files created

For each SD card, option 18 creates two separate subfolders inside the card's normal destination folder:

```text
<card destination>/
|-- Log Summary/
|   `-- data_log.txt
`-- Express Report/
    |-- express_manifest.json
    `-- <source filename>.express.bin
```

`Log Summary` contains the source filenames and file sizes. `Express Report` contains the sampled packet data and its verification manifest.

After the hub-card packages are created, option 18 also starts the existing ODO and INLB extraction sequences required by the Express Report workflow.

For a source file named:

```text
DATA.bin
```

the utility creates this file inside the `Express Report` subfolder:

```text
DATA.bin.express.bin
```

It also creates this file in the same subfolder:

```text
express_manifest.json
```

The manifest is a readable audit file. It lists the source filename, source size, packet size, Express filename, sampling interval, and every source offset that was sampled.

## Express binary layout

Each `.express.bin` file contains:

```text
20-byte file header
sample record 1
sample record 2
sample record 3
...
```

All numbers use unsigned, little-endian format.

### 20-byte header

| Bytes | Length | Contents |
| ---: | ---: | --- |
| 0-3 | 4 bytes | Text `PIGX`, identifying an Express file |
| 4-5 | 2 bytes | Format version, currently `1` |
| 6-7 | 2 bytes | Packet size: `64` or `112` |
| 8-15 | 8 bytes | Full size of the original source file |
| 16-19 | 4 bytes | Number of sampled packets |

### Sample records

Every sample record contains:

| Length | Contents |
| ---: | --- |
| 8 bytes | Packet location (byte offset) in the original file |
| 64 or 112 bytes | Original packet bytes, copied without modification |

There are no separators or padding bytes between records.

For AMFL/CMFL, each record is:

```text
8-byte source offset + 64-byte packet = 72 bytes
```

For EGP, each record is:

```text
8-byte source offset + 112-byte packet = 120 bytes
```

The total Express file size is:

```text
20 + sample count x (8 + packet size)
```

## AMFL/CMFL output example

Suppose an AMFL file contains 32,768 packets, which is exactly 2 MiB:

```text
Source size  = 2,097,152 bytes
Packets      = 32,768
Packets kept = 2 (packet 1 and packet 16,385)
Output size  = 20 + 2 x (8 + 64)
             = 164 bytes
```

The two selected 64-byte packets are copied exactly as they appear in the source file. They are not decoded, scaled, compressed, or changed.

## How IT can verify an extraction

For each sample listed in `express_manifest.json`:

1. Open the original file.
2. Go to the listed source offset.
3. Read one packet: 64 bytes for AMFL/CMFL or 112 bytes for EGP.
4. Compare those bytes with the matching packet in the `.express.bin` file.

The bytes must match exactly.

## Important limitation

Express sampling is a **sparse overview**, not a continuous copy of the recording.

For AMFL/CMFL, 16,383 out of every 16,384 packets are not included. A short event can occur between two samples and therefore be absent from the Express file.

The Express data can support quick diagnostics and line-length, temperature, and velocity analysis. It must **not** be used to prove that the original recording contained no short-duration dent, defect, or other event.
