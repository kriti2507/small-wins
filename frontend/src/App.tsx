import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./auth";
import RequireAuth from "./components/RequireAuth";
import HomePage from "./pages/HomePage";
import TopicPage from "./pages/TopicPage";
import EntryPage from "./pages/EntryPage";
import LoginPage from "./pages/LoginPage";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<RequireAuth><HomePage /></RequireAuth>} />
          <Route path="/topic/:slug" element={<RequireAuth><TopicPage /></RequireAuth>} />
          <Route
            path="/topic/:slug/entry/:id"
            element={<RequireAuth><EntryPage /></RequireAuth>}
          />
          <Route path="/login" element={<LoginPage />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
