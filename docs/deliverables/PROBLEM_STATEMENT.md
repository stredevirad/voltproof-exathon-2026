# VoltProof — problem statement

**Households and small shops on unreliable electricity can't show when, and for how long, their power
failed, because when they complain, their own memory is usually all they have to set against the
utility's records. If this worked, they could take a dated, minute-by-minute record of every outage and
voltage problem, with its uncertainty stated, to their utility or grievance forum.**

VoltProof turns the minute-by-minute voltage readings that Prayas (Energy Group) published from independent
plug-in monitors (ESMI) into traceable evidence. The analysis runs entirely inside Exasol:
- versioned SQL loads the raw files with native IMPORT;
- it unpivots them to minutes and classifies voltage with Prayas's thresholds;
- window functions find every outage.

Each outage gets exact timestamps, a certainty for each edge, and lower and upper durations. Missing data is
never counted as an outage. Interruptions that start within two minutes at other monitors in the district
are compared with a chance baseline and shown as potential shared supply events. A web app and a one-click
PDF report trace every number to its source file line and the Exasol statement that produced it, and they
point to the grievance route without claiming any entitlement.

On 102.8 million minute readings from 176 Uttar Pradesh monitors (2016–2019):
- the SQL matches an independent oracle exactly;
- single-monitor results agree with Prayas's published charts to within 0.2 hours a day;
- two defects in the published 2019 files are documented openly.
