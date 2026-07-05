import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, RequireAuth } from "./auth";
import { Layout } from "./components/Layout";
import { EvalDetailPage, EvalsPage } from "./pages/Evals";
import { LoginPage } from "./pages/Login";
import { PromotionsPage } from "./pages/Promotions";
import { ResiliencePage } from "./pages/Resilience";
import { ReviewDetailPage, ReviewsPage } from "./pages/Reviews";
import { RunDetailPage, RunsPage } from "./pages/Runs";

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            element={
              <RequireAuth>
                <Layout />
              </RequireAuth>
            }
          >
            <Route path="/" element={<Navigate to="/reviews" replace />} />
            <Route path="/reviews" element={<ReviewsPage />} />
            <Route path="/reviews/:taskId" element={<ReviewDetailPage />} />
            <Route path="/evals" element={<EvalsPage />} />
            <Route path="/evals/:runId" element={<EvalDetailPage />} />
            <Route path="/runs" element={<RunsPage />} />
            <Route path="/runs/:runId" element={<RunDetailPage />} />
            <Route path="/promotions" element={<PromotionsPage />} />
            <Route path="/resilience" element={<ResiliencePage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
