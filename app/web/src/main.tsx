import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom";
import "./styles.css";
import Home from "./pages/Home";
import LocationMonth from "./pages/LocationMonth";
import DayView from "./pages/DayView";
import EventView from "./pages/EventView";
import GroupView from "./pages/GroupView";
import Methodology from "./pages/Methodology";
import Sources from "./pages/Sources";

function Layout() {
  return (
    <>
      <header className="top">
        <a className="brand" href="/">VoltProof<small>evidence of power cuts and poor supply</small></a>
        <nav className="main" aria-label="Main">
          <NavLink to="/" end>Start</NavLink>
          <NavLink to="/methodology">Methodology</NavLink>
          <NavLink to="/sources">Data &amp; sources</NavLink>
        </nav>
      </header>
      <main className="shell">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/location/:id/:month" element={<LocationMonth />} />
          <Route path="/location/:id/day/:day" element={<DayView />} />
          <Route path="/event/:key" element={<EventView />} />
          <Route path="/group" element={<GroupView />} />
          <Route path="/methodology" element={<Methodology />} />
          <Route path="/sources" element={<Sources />} />
          <Route path="*" element={<p>Page not found. <a href="/">Go to the start page.</a></p>} />
        </Routes>
      </main>
      <footer className="bottom">
        Data: Prayas (Energy Group), Electricity Supply Monitoring Initiative (ESMI), Harvard Dataverse
        doi:10.7910/DVN/CLLZZM (CC0 1.0), cited as the dataset page requires. All figures are computed from these
        real measurements; no figure in this app is illustrative or simulated. VoltProof is an evidence-analysis aid,
        not legal advice or an official determination.
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
