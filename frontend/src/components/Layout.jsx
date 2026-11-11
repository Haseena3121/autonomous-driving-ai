import { useEffect, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import Sidebar from './Sidebar.jsx';
import TopBar from './TopBar.jsx';

const TITLES = {
  '/': { title: 'Home Dashboard', subtitle: 'System overview and real model status' },
  '/detection': { title: 'Object Detection', subtitle: 'Run your trained YOLO model on images' },
  '/video-analysis': { title: 'Video Analysis', subtitle: 'Frame-by-frame YOLO inference on uploaded videos' },
  '/tracking': { title: 'Object Tracking', subtitle: 'ByteTrack multi-object tracking with trajectories' },
  '/lane-detection': { title: 'Lane Detection', subtitle: 'OpenCV Canny + Hough pipeline and deep segmentation comparison' },
  '/depth-estimation': { title: 'Depth Estimation', subtitle: 'MiDaS relative monocular depth' },
  '/simulation': { title: 'Autonomous Driving Simulation', subtitle: 'CARLA live perception bridge and ROS2 module' },
  '/doubts': { title: 'Doubts Assistant', subtitle: 'Ask questions about model training, pipelines, and troubleshooting' },
};

export default function Layout() {
  const [menuOpen, setMenuOpen] = useState(false);
  const { pathname } = useLocation();

  useEffect(() => {
    setMenuOpen(false);
    window.scrollTo(0, 0);
  }, [pathname]);

  const meta = TITLES[pathname] || TITLES['/'];

  return (
    <div className="app-shell">
      <Sidebar open={menuOpen} onClose={() => setMenuOpen(false)} />
      <div className={`sidebar-overlay ${menuOpen ? 'visible' : ''}`} onClick={() => setMenuOpen(false)} />
      <div className="main-area">
        <TopBar title={meta.title} subtitle={meta.subtitle} onToggleMenu={() => setMenuOpen((v) => !v)} />
        <main className="page">
          <Outlet />
        </main>
        <footer className="footer">
          AI-Based Autonomous Driving System — Object Detection · Tracking · Lane Detection · Depth Estimation · Obstacle Avoidance
        </footer>
      </div>
    </div>
  );
}
