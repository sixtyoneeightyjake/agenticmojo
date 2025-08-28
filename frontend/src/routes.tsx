import { BrowserRouter, Routes, Route } from "react-router-dom";
import AgentMojoArcadeLanding from "./App";
import P1Run from "./pages/P1Run";
import P2Interactive from "./pages/P2Interactive";

export default function AppRoutes() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AgentMojoArcadeLanding />} />
        <Route path="/p1" element={<P1Run />} />
        <Route path="/p2" element={<P2Interactive />} />
      </Routes>
    </BrowserRouter>
  );
}

