import { Route, Routes } from "react-router-dom";

import { Dashboard } from "./pages/Dashboard";
import { MachineDetail } from "./pages/MachineDetail";

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/machine/:machineId" element={<MachineDetail />} />
      <Route path="*" element={<Dashboard />} />
    </Routes>
  );
}
