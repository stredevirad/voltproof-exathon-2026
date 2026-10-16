import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { uploads } from "./api";

/** Optional first-visit tour of the start page (Part 4): a small card that points at four things in turn. Skippable at
 *  every step, reopenable from the "How to use" page (?tour=1), and it works on every dataset. Whether it was seen is
 *  kept in this browser's localStorage; if storage is blocked, the tour simply shows again next time. Automated
 *  browsers (tests, screenshots, the demo recording) never get it unless the address asks for it with ?tour=1. */
const KEY = "voltproof.tourSeen";

function seen(): boolean {
  try { return window.localStorage.getItem(KEY) === "1"; } catch { return false; }
}

let closedThisVisit = false;  // also when storage is blocked, a closed tour stays closed until the page is reloaded

function markSeen() {
  closedThisVisit = true;
  try { window.localStorage.setItem(KEY, "1"); } catch { /* storage blocked: nothing to remember */ }
}

type Step = { target?: string; title: string; text: string };
const STEPS: Step[] = [
  { title: "Welcome to VoltProof", text: "VoltProof turns minute-by-minute voltage records into evidence of power cuts. " +
      "This short tour shows where things are. You can skip it at any time." },
  { target: "guided-demo", title: "The fastest start", text: "Open one example month, chosen by a fixed rule, and follow " +
      "it from the month to a single day and one power cut." },
  { target: "state-select", title: "Pick a place", text: "Or choose a state here. Then choose a district. Then pick a " +
      "monitored location in the table, and one of its months." },
  { target: "dataset-select", title: "Which data you see", text: "Switch between the datasets on this computer: the real " +
      "Prayas data, the SYNTHETIC demo set, and any file you uploaded. Each page says which one it shows." },
  { target: "nav-guide", title: "The full guide", text: "“How to use” explains every colour and number in plain words. " +
      "You can start this tour again from there." },
];

export function Tour() {
  const [sp, setSp] = useSearchParams();
  const asked = sp.get("tour") === "1";
  const [open, setOpen] = useState(false);
  const [i, setI] = useState(0);
  const card = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (asked || (!closedThisVisit && !seen() && !navigator.webdriver)) { setI(0); setOpen(true); }
  }, [asked]);

  // the dataset switcher (and its step) appears only when this computer has two or more datasets
  const [several, setSeveral] = useState(false);
  useEffect(() => { uploads.datasets().then((d) => setSeveral(d.length >= 2)).catch(() => setSeveral(false)); }, []);
  const steps = STEPS.filter((s) => s.target !== "dataset-select" || several);
  const step = steps[Math.min(i, steps.length - 1)];

  useEffect(() => {
    if (!open || !step?.target) return;
    const el = document.querySelector<HTMLElement>(`[data-testid="${step.target}"]`);
    if (!el) return;
    el.classList.add("tour-target");
    el.scrollIntoView({ block: "center", behavior: "auto" });
    return () => el.classList.remove("tour-target");
  }, [open, step]);

  useEffect(() => { if (open) card.current?.focus(); }, [open, i]);

  const close = useCallback(() => {
    markSeen();
    setOpen(false);
    if (asked) {
      const next = new URLSearchParams(sp);
      next.delete("tour");
      setSp(next, { replace: true });
    }
  }, [asked, sp, setSp]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") close(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, close]);

  if (!open || !step) return null;
  const last = i >= steps.length - 1;
  return (
    <div className="tour" role="dialog" aria-modal="false" aria-labelledby="tour-title" tabIndex={-1} ref={card}
         data-testid="tour">
      <p className="small muted" style={{ margin: 0 }}>Tour, step {Math.min(i, steps.length - 1) + 1} of {steps.length}</p>
      <h2 id="tour-title">{step.title}</h2>
      <p>{step.text}</p>
      <div className="row" style={{ alignItems: "center" }}>
        {i > 0 && <button type="button" onClick={() => setI(i - 1)} data-testid="tour-back">Back</button>}
        {last
          ? <button type="button" className="primary" onClick={close} data-testid="tour-done">Done</button>
          : <button type="button" className="primary" onClick={() => setI(i + 1)} data-testid="tour-next">Next</button>}
        {!last && <button type="button" className="link" onClick={close} data-testid="tour-skip">Skip the tour</button>}
      </div>
    </div>
  );
}
