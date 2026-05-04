import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import AppLayout from './components/layout/AppLayout';
import Trends from './pages/Trends';
import Searches from './pages/Searches';
import BlogPost from './pages/BlogPost';
import LinkedInPost from './pages/LinkedInPost';
import Insights from './pages/Insights';
import InternalUpdates from './pages/InternalUpdates';
import SlackPost from './pages/SlackPost';
import { TimeProvider } from './context/TimeContext';
import { WorkspaceProvider } from './context/WorkspaceContext';
import { BackendStatusProvider } from './context/BackendStatusContext';
import { SearchModeProvider } from './context/SearchModeContext';

export default function App() {
  return (
    <WorkspaceProvider>
      <BackendStatusProvider>
        <SearchModeProvider>
          <TimeProvider>
            <Router>
              <AppLayout>
                <Routes>
                  <Route path="/" element={<Trends />} />
                  <Route path="/searches" element={<Searches />} />
                  <Route path="/insights" element={<Insights />} />
                  <Route path="/blog-post" element={<BlogPost />} />
                  <Route path="/linkedin-post" element={<LinkedInPost />} />
                  <Route path="/updates" element={<InternalUpdates />} />
                  <Route path="/slack-post" element={<SlackPost />} />
                  <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
              </AppLayout>
            </Router>
          </TimeProvider>
        </SearchModeProvider>
      </BackendStatusProvider>
    </WorkspaceProvider>
  );
}
