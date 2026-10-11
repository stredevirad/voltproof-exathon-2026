# Data source, licence and terms

VoltProof analyses **real, public** voltage measurements from the **Electricity Supply Monitoring
Initiative (ESMI)** run by **Prayas (Energy Group)**, Pune, India. No employer, proprietary or personal
data is used. The only synthetic data in this repository is the small hand-written test fixtures in
`tests/fixtures/`, which are labelled as synthetic.

## Source

| Field | Value |
|---|---|
| Title | Minute-wise voltage data collected in Electricity Supply Monitoring Initiative |
| Author / depositor | Prayas, Energy Group |
| Repository | Harvard Dataverse |
| Persistent ID | `doi:10.7910/DVN/CLLZZM` (https://doi.org/10.7910/DVN/CLLZZM) |
| Version | 2.0, released 2021-02-18 |
| Contact | esmi@prayaspune.org |
| Coverage | November 2014 – December 2019 (14 files) |
| Retrieved | 2026-10-11 via the Dataverse native API (`/api/datasets/:persistentId/?persistentId=doi:10.7910/DVN/CLLZZM`) |

**Suggested citation:** Prayas (Energy Group), "Minute-wise voltage data collected in Electricity Supply
Monitoring Initiative", Harvard Dataverse, V2, doi:10.7910/DVN/CLLZZM.

## Licence (dataset metadata)

The dataset's licence field on Harvard Dataverse is:

> **CC0 1.0** — http://creativecommons.org/publicdomain/zero/1.0 (SPDX: `CC0-1.0`)

## Prayas's terms of use (dataset description)

The dataset description also contains this text, quoted verbatim:

> "The information made available on the website and through ESMI is made available on 'as is where is'
> basis. Though reasonable care is taken to provide reliable data, neither Prayas, nor any of its agents,
> contractors, employees can be held responsible for use of any data or information made available
> herein. Anybody is welcome to make full use of the information available herein for any
> non-commercial, academic and research purpose, provided source of the information is clearly
> acknowledged. We will highly appreciate if we are intimated of use of this data and a copy of the
> publication, paper or report using this data is shared with us at esmi@prayaspune.org"

Prayas's ESMI pages also say: "The minute-wise voltage data collected through ESMI is available in the
public domain on watchyourpower.org and the Harvard Dataverse."
(https://energy.prayaspune.org/how-does-esmi-work, retrieved 2026-10-11)

## How VoltProof complies (stricter of the two readings)

1. **Attribution everywhere the data appears:** README, app footer, every evidence report, the pitch deck.
2. **No redistribution of raw data.** Raw files are never committed; `.gitignore` blocks `data/`, `*.csv`,
   `*.tab`. Each user downloads the files from Harvard Dataverse.
3. **Non-commercial, research and demonstration use.** VoltProof is MIT-licensed open-source software
   entered in a free public hackathon. It is not a commercial product.
4. **Notification.** The team notifies Prayas of this use by email (sent by a team member, not by the software).

The MIT licence in `LICENSE` covers **code only**. It does not cover the ESMI data.

## Download gate (Guestbook)

Every file download on Harvard Dataverse requires a **Guestbook** response (guestbook 251, "ESMI
guestbook"). The required fields are name, email, institution, position, and "Brief description of the
intended use of the downloaded data." There are two ways to provide it:

- **Browser:** download the files from the dataset page and save them in `data\raw\` with names unchanged.
  For tabular files, pick **"Original File Format (Comma Separated Values)"**.
- **Script:** fill the `DATAVERSE_GB_*` fields in your own `.env`. `scripts\get-data.ps1 -Download` then
  submits **your** guestbook response through the Dataverse Data Access API (a POST with a
  `guestbookResponse` body returns a signed download URL).

`scripts\get-data.ps1` then verifies every file against the MD5 checksum that Dataverse publishes, and
writes `data\manifest.json` (file names, sizes, MD5 and SHA-256, retrieval time). Personal details
are never written to the manifest, the logs or the repository.

## Files in the dataset

| File (original format) | Bytes (original) | MD5 (Dataverse) | Needed for |
|---|---:|---|---|
| ESMI location information.csv | 49,868 | f3e785dd06350a6c8e714ceca9b743a7 | always |
| About the initiative.pdf | 644,407 | 99f8e09691a8c91afc18d3edf251e3b5 | documentation |
| ESMI minute-wise voltage data 2014.csv | 15,134,529 | 2e78dafcbdc21e46b91d59b851ddf90a | not used |
| ESMI minute-wise voltage data 2015.csv | 202,762,276 | f75a2dbbfe919c251d14f4aff60c03cd | not used |
| ESMI minute-wise voltage data 2016 Jan-June.csv | 206,629,089 | 8dd65bc2b0c53e0a9c175227c4b2d8d7 | UP validation |
| ESMI minute-wise voltage data 2016 July-Dec.csv | 233,023,214 | 71ad77c54751f9144182ed99e087eac0 | UP validation |
| ESMI minute-wise voltage data 2017 Jan-April.csv | 185,595,068 | 5ba4b3740a05915d9bf543c5288e6c57 | UP validation |
| ESMI minute-wise voltage data 2017 May-Aug.csv | 179,365,840 | 0496a9947e0db3bc975d5673b03c94d6 | UP validation |
| ESMI minute-wise voltage data 2017 Sept-Dec.csv | 166,259,841 | 79743b956ce2650ab56ba7c84504756c | UP validation |
| ESMI minute-wise voltage data 2018 Jan-May.csv | 229,538,374 | dca37d4bb46a30a8f825d77010e5436d | UP validation |
| ESMI minute-wise voltage data 2018 June-Aug.csv | 140,188,421 | b6285ccb38c3865f525ef44f7f1d7fdc | **first sample** |
| ESMI minute-wise voltage data 2018 Sep-Dec.csv | 178,921,174 | 6696429f53962a05cf065ba3a6148e56 | UP validation |
| ESMI voltage data 2019 Jan-June.csv | 241,193,056 | e9eb381f27463f8b231edd59b4bde9af | UP validation |
| ESMI voltage data 2019 July-Dec.csv | 186,876,236 | 33fda7b61888a40ba3ebfe11dc18d819 | UP validation |

The listed MD5 is the value Dataverse publishes. The verification script checks it against the
original-format file and reports exactly which variant it saw. Whether the MD5 refers to the original
CSV or to the ingested tab export **is verified on the first download** (see VERIFICATION_LOG).

## What the data means (Prayas's own statements)

- "A '0' voltage reading means a power outage."
- "Missing data should be interpreted as unavailable data and not as interruption."
- "Certain locations have been marked as [Offline], which indicates that the monitoring at the locations
  has been discontinued."
- The monitor "measures and records voltage with an accuracy of +/- 4 V … for every minute".
- Voltage classes (https://energy.prayaspune.org/how-does-esmi-work): Normal 205–270 V; Low 131–204 V;
  High above 271 V; "Voltage below 131 (i.e. 130 and less) is considered as no supply".
