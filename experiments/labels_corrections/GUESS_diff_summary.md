# GUESS label correction — proposed diff
Source xlsx: `dataset/GUESS ATHLEISURE - MAIN FALL 26 MASTER FILE #1.xlsx`
Source labels: `dataset/extracted/GUESS ATHLEISURE - MAIN FALL 26 MASTER FILE #1.json`
Proposed output: `experiments/labels_corrections/GUESS_proposed.json` (not yet applied)

## Summary
- PLI count: **170** (unchanged)
- io_number changes: **170** (all PLIs)
- New metadata entries added: **170** (one PO NO entry per PLI)

## First 15 PLI changes

| PLI | xlsx row | io_number OLD (PO) | io_number NEW (ION) | metadata added |
|---|---|---|---|---|
| 0 | row 2 | `MA01-2026-00325` | `1091` | `PO NO: MA01-2026-00325` |
| 1 | row 3 | `MA03-2026-00367` | `1091` | `PO NO: MA03-2026-00367` |
| 2 | row 4 | `MA03-2026-00368` | `1091` | `PO NO: MA03-2026-00368` |
| 3 | row 5 | `MX01-2026-00214` | `1091` | `PO NO: MX01-2026-00214` |
| 4 | row 8 | `MA01-2026-00330` | `1096` | `PO NO: MA01-2026-00330` |
| 5 | row 9 | `MA01-2026-00330` | `1096` | `PO NO: MA01-2026-00330` |
| 6 | row 10 | `MA01-2026-00330` | `1096` | `PO NO: MA01-2026-00330` |
| 7 | row 11 | `MA03-2026-00375` | `1096` | `PO NO: MA03-2026-00375` |
| 8 | row 12 | `MA03-2026-00376` | `1096` | `PO NO: MA03-2026-00376` |
| 9 | row 15 | `MA01-2026-00335` | `1093` | `PO NO: MA01-2026-00335` |
| 10 | row 16 | `SP01-2026-00099` | `1093` | `PO NO: SP01-2026-00099` |
| 11 | row 17 | `IN01-2026-00026` | `1093` | `PO NO: IN01-2026-00026` |
| 12 | row 18 | `MA01-2026-00335` | `1093` | `PO NO: MA01-2026-00335` |
| 13 | row 19 | `MX01-2026-00217` | `1093` | `PO NO: MX01-2026-00217` |
| 14 | row 20 | `IN01-2026-00026` | `1093` | `PO NO: IN01-2026-00026` |

## Last 5 PLI changes

| PLI | xlsx row | io_number OLD (PO) | io_number NEW (ION) | metadata added |
|---|---|---|---|---|
| 165 | row 193 | `MA01-2026-01254` | `1166` | `PO NO: MA01-2026-01254` |
| 166 | row 194 | `MA02-2026-00587` | `1166` | `PO NO: MA02-2026-00587` |
| 167 | row 195 | `MA03-2026-01173` | `1166` | `PO NO: MA03-2026-01173` |
| 168 | row 196 | `MA03-2026-01174` | `1166` | `PO NO: MA03-2026-01174` |
| 169 | row 197 | `SP01-2026-00320` | `1166` | `PO NO: SP01-2026-00320` |

## New io_number distribution

Distinct values: **14** (was 54 distinct PO values)

| ION | # PLIs |
|---|---|
| 1091 | 4 |
| 1092 | 8 |
| 1093 | 12 |
| 1094 | 24 |
| 1096 | 5 |
| 1136 | 8 |
| 1144 | 16 |
| 1152 | 17 |
| 1158 | 29 |
| 1163 | 17 |
| 1164 | 4 |
| 1166 | 5 |
| 1193 | 16 |
| 1195 | 5 |
