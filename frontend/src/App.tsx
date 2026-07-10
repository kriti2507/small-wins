import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./auth";
import HomePage from "./pages/HomePage";
import TopicPage from "./pages/TopicPage";
import EntryPage from "./pages/EntryPage";
import LoginPage from "./pages/LoginPage";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/topic/:slug" element={<TopicPage />} />
          <Route path="/topic/:slug/entry/:id" element={<EntryPage />} />
          <Route path="/login" element={<LoginPage />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
