import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { AppShell } from "./components/AppShell";
import { LandingPage } from "./pages/Landing";
import { LoginPage } from "./pages/Login";
import { RegisterPage } from "./pages/Register";
import { DashboardPage } from "./pages/Dashboard";
import { MarketsPage } from "./pages/Markets";
import { PortfolioPage } from "./pages/Portfolio";
import { WatchlistPage } from "./pages/Watchlist";
import { TradingPage } from "./pages/Trading";
import { OrdersPage } from "./pages/Orders";
import { TransactionsPage } from "./pages/Transactions";
import { ProfilePage } from "./pages/Profile";
import { SettingsPage } from "./pages/Settings";
import { AdminPage } from "./pages/Admin";
import { NewsPage } from "./pages/News";
import { AnalyticsPage } from "./pages/Analytics";
import { AiAssistantPage } from "./pages/AiAssistant";

function HomeRoute() {
  // An authenticated visitor landing on "/" goes straight to the app instead
  // of seeing the marketing page again — everyone else sees the landing page.
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return null;
  return isAuthenticated ? <Navigate to="/app/dashboard" replace /> : <LandingPage />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomeRoute />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route
        path="/app/dashboard"
        element={
          <ProtectedRoute>
            <AppShell>
              <DashboardPage />
            </AppShell>
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/watchlist"
        element={
          <ProtectedRoute>
            <AppShell>
              <WatchlistPage />
            </AppShell>
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/markets"
        element={
          <ProtectedRoute>
            <AppShell>
              <MarketsPage />
            </AppShell>
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/portfolio"
        element={
          <ProtectedRoute>
            <AppShell>
              <PortfolioPage />
            </AppShell>
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/trading"
        element={
          <ProtectedRoute>
            <AppShell>
              <TradingPage />
            </AppShell>
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/orders"
        element={
          <ProtectedRoute>
            <AppShell>
              <OrdersPage />
            </AppShell>
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/transactions"
        element={
          <ProtectedRoute>
            <AppShell>
              <TransactionsPage />
            </AppShell>
          </ProtectedRoute>
        }
      />

      <Route
        path="/app/profile"
        element={
          <ProtectedRoute>
            <AppShell>
              <ProfilePage />
            </AppShell>
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/settings"
        element={
          <ProtectedRoute>
            <AppShell>
              <SettingsPage />
            </AppShell>
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/admin"
        element={
          <ProtectedRoute>
            <AppShell>
              <AdminPage />
            </AppShell>
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/news"
        element={
          <ProtectedRoute>
            <AppShell>
              <NewsPage />
            </AppShell>
          </ProtectedRoute>
        }
      />
      <Route
        path="/app/analytics"
        element={
          <ProtectedRoute>
            <AppShell>
              <AnalyticsPage />
            </AppShell>
          </ProtectedRoute>
        }
      />

      <Route
        path="/app/assistant"
        element={
          <ProtectedRoute>
            <AppShell>
              <AiAssistantPage />
            </AppShell>
          </ProtectedRoute>
        }
      />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
