import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AuthProvider } from "./auth/AuthContext";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { AdminLayout } from "./components/AdminLayout";
import { AdminRoute } from "./components/AdminRoute";
import { AppLayout } from "./components/AppLayout";
import { AboutPage } from "./pages/AboutPage";
import { AdminAIUsagePage } from "./pages/AdminAIUsagePage";
import { AdminCatalogPage } from "./pages/AdminCatalogPage";
import { AdminOverviewPage } from "./pages/AdminOverviewPage";
import { AdminUserDetailPage } from "./pages/AdminUserDetailPage";
import { AdminUsersPage } from "./pages/AdminUsersPage";
import { AppHomePage } from "./pages/AppHomePage";
import { AuthPage } from "./pages/AuthPage";
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage";
import { LearnPage } from "./pages/LearnPage";
import { PracticePage } from "./pages/PracticePage";
import { ResetPasswordPage } from "./pages/ResetPasswordPage";
import { ReviewPage } from "./pages/ReviewPage";
import { VocabularyEditorPage } from "./pages/VocabularyEditorPage";
import { VocabularyPage } from "./pages/VocabularyPage";
import { VocabularySetPage } from "./pages/VocabularySetPage";

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<AuthPage mode="login" />} />
          <Route path="/register" element={<AuthPage mode="register" />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route
            path="/admin"
            element={
              <AdminRoute>
                <AdminLayout />
              </AdminRoute>
            }
          >
            <Route index element={<AdminOverviewPage />} />
            <Route path="users" element={<AdminUsersPage />} />
            <Route path="users/:userId" element={<AdminUserDetailPage />} />
            <Route path="catalog" element={<AdminCatalogPage />} />
            <Route path="ai-usage" element={<AdminAIUsagePage />} />
          </Route>
          <Route
            path="/app"
            element={
              <ProtectedRoute>
                <AppLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<AppHomePage />} />
            <Route path="learn" element={<LearnPage />} />
            <Route path="learn/sets/:setId" element={<VocabularySetPage />} />
            <Route path="review" element={<ReviewPage />} />
            <Route path="practice" element={<PracticePage />} />
            <Route path="vocabulary" element={<VocabularyPage />} />
            <Route path="vocabulary/new" element={<VocabularyEditorPage />} />
            <Route path="vocabulary/:vocabularyId/edit" element={<VocabularyEditorPage />} />
            <Route path="about" element={<AboutPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/app" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
