import { StrictMode, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { CURRENT_DS, withDs } from "./api";
import "./styles.css";
import Home from "./pages/Home";
import LocationMonth from "./pages/LocationMonth";
import DayView from "./pages/DayView";
import EventView from "./pages/EventView";
import GroupView from "./pages/GroupView";
import Methodology from "./pages/Methodology";
import Sources from "./pages/Sources";
import Upload from "./pages/Upload";
import { DatasetSwitcher, SyntheticBanner, UploadBanner, useDataset } from "./ui";

/** Keeps the dataset in the address bar when a link leaves it out, so a reload or a shared link stays on it. */
function KeepDataset() {
  const loc = useLocation();
  const nav = useNavigate();
  useEffect(() => {
    if (CURRENT_DS && loc.pathname !== "/upload" && !new URLSearchParams(loc.search).get("ds")) {
      nav(withDs(loc.pathname + loc.search) + loc.hash, { replace: true });
    }
  }, [loc, nav]);
  return null;
}

function Layout() {
  const ds = useDataset();
  return (
    <>
      <KeepDataset />
      <header className="top">
        <a className="brand" href={withDs("/")}>VoltProof<small>evidence of power cuts and poor supply</small></a>
        <nav className="main" aria-label="Main">
          <NavLink to={withDs("/")} end>Start</NavLink>
          <NavLink to={withDs("/methodology")}>Methodology</NavLink>
          <NavLink to={withDs("/sources")}>Data &amp; sources</NavLink>
          <NavLink to="/upload">Upload your data</NavLink>
        </nav>
        <DatasetSwitcher />
      </header>
      <SyntheticBanner />
      <UploadBanner />
      <main className="shell">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/location/:id/:month" element={<LocationMonth />} />
          <Route path="/location/:id/day/:day" element={<DayView />} />
          <Route path="/event/:key" element={<EventView />} />
          <Route path="/group" element={<GroupView />} />
          <Route path="/methodology" element={<Methodology />} />
          <Route path="/sources" element={<Sources />} />
          <Route path="/upload" element={<Upload />} />
          <Route path="*" element={<p>Page not found. <a href="/">Go to the start page.</a></p>} />
        </Routes>
      </main>
      <footer className="bottom">
        {!ds && CURRENT_DS ? null : ds?.kind === "upload" ? (
          <>UPLOADED DATA: every figure on these pages comes from the uploaded file “{ds.upload?.file_name}”, which
            VoltProof has not verified. VoltProof is an evidence-analysis aid, not legal advice or an official
            determination.</>
        ) : ds?.synthetic ? (
          <>SYNTHETIC DEMO DATA: every figure in this build comes from invented readings (pipeline/synthetic.py) in the
            ESMI file format; none describes real supply. VoltProof is an evidence-analysis aid, not legal advice or an
            official determination.</>
        ) : (
          <>Data: Prayas (Energy Group), Electricity Supply Monitoring Initiative (ESMI), Harvard Dataverse
            doi:10.7910/DVN/CLLZZM (CC0 1.0), cited as the dataset page requires. All figures are computed from these
            real measurements; no figure in this app is illustrative or simulated. VoltProof is an evidence-analysis aid,
            not legal advice or an official determination.</>
        )}
      </footer>
    </>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Layout />
    </BrowserRouter>
  </StrictMode>,
);
