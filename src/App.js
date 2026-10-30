import React from 'react';
import { Routes, Route } from 'react-router-dom';
import CleanAIHelp from './pages/individual/assistant/CleanAIHelp.js';
import IndividualLayout from './components/layout/IndividualLayout.js';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<IndividualLayout />}>
        <Route path="individual/clean-help" element={<CleanAIHelp />} />
      </Route>
      <Route path="/individual/clean-help" element={<CleanAIHelp />} />
    </Routes>
  );
}
export { CleanAIHelp, IndividualLayout };
