import { BrowserRouter as Router, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import AppLayout from './components/layout/AppLayout';
import ProtectedRoute from './components/ProtectedRoute';
import Trends from './pages/Trends';
import Searches from './pages/Searches';
import BlogPost from './pages/BlogPost';
import LinkedInPost from './pages/LinkedInPost';
import Insights from './pages/Insights';
import InternalUpdates from './pages/InternalUpdates';
import SlackPost from './pages/SlackPost';
import Login from './pages/Login';
import { TimeProvider } from './context/TimeContext';
import { WorkspaceProvider } from './context/WorkspaceContext';
import { BackendStatusProvider } from './context/BackendStatusContext';
import { SearchModeProvider } from './context/SearchModeContext';
import { ToastProvider } from './context/ToastContext';
import { AuthProvider } from './context/AuthContext';
import ToastViewport from './components/ToastViewport';

function AppShell() {
  return <AppLayout><Outlet /></AppLayout>;
}

export default function App() {
  return (
    <WorkspaceProvider>
      <SearchModeProvider>
        <ToastProvider>
          <TimeProvider>
            <Router>
              <AuthProvider>
                <Routes>
                  <Route path="/login" element={<Login />} />
                  <Route element={<ProtectedRoute />}>
                    <Route
                      element={
                        <BackendStatusProvider>
                          <AppShell />
                        </BackendStatusProvider>
                      }
                    >
                      <Route path="/" element={<Trends />} />
                      <Route path="/searches" element={<Searches />} />
                      <Route path="/insights" element={<Insights />} />
                      <Route path="/blog-post" element={<BlogPost />} />
                      <Route path="/linkedin-post" element={<LinkedInPost />} />
                      <Route path="/updates" element={<InternalUpdates />} />
                      <Route path="/slack-post" element={<SlackPost />} />
                      <Route path="*" element={<Navigate to="/" replace />} />
                    </Route>
                  </Route>
                </Routes>
                <ToastViewport />
              </AuthProvider>
            </Router>
          </TimeProvider>
        </ToastProvider>
      </SearchModeProvider>
    </WorkspaceProvider>
  );
}
