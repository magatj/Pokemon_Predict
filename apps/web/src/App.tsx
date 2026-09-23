import { Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { About } from "./pages/About";
import { Dashboard } from "./pages/Dashboard";
import { MachineDetail } from "./pages/MachineDetail";
import { Sources } from "./pages/Sources";

export function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/machine/:machineId" element={<MachineDetail />} />
        <Route path="/sources" element={<Sources />} />
        <Route path="/about" element={<About />} />
        <Route path="*" element={<Dashboard />} />
      </Routes>
    </AppShell>
  );
}
