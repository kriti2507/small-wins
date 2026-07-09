import { BrowserRouter, Routes, Route } from "react-router-dom";
import HomePage from "./pages/HomePage";
import TopicPage from "./pages/TopicPage";
import EntryPage from "./pages/EntryPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/topic/:slug" element={<TopicPage />} />
        <Route path="/topic/:slug/entry/:id" element={<EntryPage />} />
      </Routes>
    </BrowserRouter>
  );
}
