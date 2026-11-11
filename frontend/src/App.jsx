import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext.jsx';
import Layout from './components/Layout.jsx';
import Dashboard from './pages/Dashboard.jsx';
import ObjectDetection from './pages/ObjectDetection.jsx';
import VideoAnalysis from './pages/VideoAnalysis.jsx';
import ObjectTracking from './pages/ObjectTracking.jsx';
import LaneDetection from './pages/LaneDetection.jsx';
import DepthEstimation from './pages/DepthEstimation.jsx';
import DrivingSimulation from './pages/DrivingSimulation.jsx';
import DoubtsChatbox from './pages/DoubtsChatbox.jsx';
import LoginPage from './pages/LoginPage.jsx';

function AppContent() {
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/detection" element={<ObjectDetection />} />
        <Route path="/video-analysis" element={<VideoAnalysis />} />
        <Route path="/tracking" element={<ObjectTracking />} />
        <Route path="/lane-detection" element={<LaneDetection />} />
        <Route path="/depth-estimation" element={<DepthEstimation />} />
        <Route path="/simulation" element={<DrivingSimulation />} />
        <Route path="/doubts" element={<DoubtsChatbox />} />
        <Route path="/performance" element={<Navigate to="/doubts" replace />} />
        <Route path="/model-info" element={<Navigate to="/doubts" replace />} />
        <Route path="/documentation" element={<Navigate to="/doubts" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </BrowserRouter>
  );
}
