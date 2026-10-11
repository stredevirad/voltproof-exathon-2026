# VoltProof — problem statement

Many Indian households and small shops live with daily power cuts and unusable voltage. When they
complain, their memory is the only record, against the utility's own reports. Prayas (Energy Group)
published minute-by-minute readings from independent plug-in monitors (ESMI), but the raw files, 63-column
hourly rows with gaps, duplicates and defects, are not evidence anyone can use.

VoltProof turns those records into traceable evidence, entirely inside Exasol. Versioned SQL steps load
the files with native IMPORT, unpivot them to minutes, classify voltage with Prayas's thresholds, and find
every outage with window functions. Each outage gets exact timestamps, a certainty for each edge and
lower and upper durations; missing data is never counted as an outage. A chance-controlled comparison
flags potential shared supply events, where monitors in a district lost supply within two minutes of each
other. A web app and a one-click PDF report trace every number to the source file line and the Exasol
statement that produced it, and point to the statutory grievance route without claiming any entitlement.

On 102.8 million minute readings from 176 Uttar Pradesh monitors (2016–2019), the SQL matches an
independent oracle exactly. Single-monitor results agree with Prayas's published charts to within
0.2 hours a day, and the work uncovered two defects in the published 2019 files, which it documents
openly. VoltProof gives consumers, researchers and regulators a reproducible way to see how
reliable supply really was.
