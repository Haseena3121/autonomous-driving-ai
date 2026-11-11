import { useEffect, useRef, useState } from 'react';
import PageHeader from '../components/PageHeader.jsx';

export default function DrivingSimulation() {
  // Simulator controls
  const [isRunning, setIsRunning] = useState(true);
  const [drivingMode, setDrivingMode] = useState('autonomous'); // 'autonomous' | 'manual'
  const [targetSpeed, setTargetSpeed] = useState(70);
  const [weather, setWeather] = useState('day'); // 'day' | 'night' | 'rain'
  const [scenario, setScenario] = useState('highway'); // 'highway' | 'obstacle' | 'curves'
  
  // User input states (keys/pedals)
  const inputRef = useRef({
    gas: false,
    brake: false,
    left: false,
    right: false,
  });

  const [activePedal, setActivePedal] = useState({ gas: false, brake: false });

  // Telemetry state
  const [telemetry, setTelemetry] = useState({
    speed: 68,
    steeringAngle: 0.8,
    laneOffset: -0.04,
    closestObstacle: 34.2,
    ttc: 6.8,
    leadId: 104,
    leadClass: 'Car',
    leadConf: 94,
    safetyStatus: 'SAFE',
    throttle: 42,
    brake: 0,
    fps: 60,
  });

  const canvasRef = useRef(null);

  // -------------------------------------------------------------------------
  // Keyboard Listeners for Manual Driving & Braking (Space / W / A / S / D / Arrows)
  // -------------------------------------------------------------------------
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Prevent page scrolling on space and arrow keys
      if (['Space', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.code)) {
        e.preventDefault();
      }

      if (e.code === 'Space' || e.code === 'ArrowDown' || e.key === 's' || e.key === 'S') {
        inputRef.current.brake = true;
        setActivePedal((p) => ({ ...p, brake: true }));
      }
      if (e.code === 'ArrowUp' || e.key === 'w' || e.key === 'W') {
        inputRef.current.gas = true;
        setActivePedal((p) => ({ ...p, gas: true }));
      }
      if (e.code === 'ArrowLeft' || e.key === 'a' || e.key === 'A') {
        inputRef.current.left = true;
      }
      if (e.code === 'ArrowRight' || e.key === 'd' || e.key === 'D') {
        inputRef.current.right = true;
      }
    };

    const handleKeyUp = (e) => {
      if (e.code === 'Space' || e.code === 'ArrowDown' || e.key === 's' || e.key === 'S') {
        inputRef.current.brake = false;
        setActivePedal((p) => ({ ...p, brake: false }));
      }
      if (e.code === 'ArrowUp' || e.key === 'w' || e.key === 'W') {
        inputRef.current.gas = false;
        setActivePedal((p) => ({ ...p, gas: false }));
      }
      if (e.code === 'ArrowLeft' || e.key === 'a' || e.key === 'A') {
        inputRef.current.left = false;
      }
      if (e.code === 'ArrowRight' || e.key === 'd' || e.key === 'D') {
        inputRef.current.right = false;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, []);

  // -------------------------------------------------------------------------
  // 60 FPS HTML5 Canvas Autonomous Driving Simulation Engine
  // -------------------------------------------------------------------------
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId;
    let roadOffset = 0;
    let curveAngle = 0;
    let currentSpeed = 65;
    let currentSteer = 0;
    let obstacleDistance = 45;
    let obstacleSpeed = 60;
    let userLateralOffset = 0; // manual steering lateral shift
    let rainDrops = Array.from({ length: 70 }, () => ({
      x: Math.random() * 960,
      y: Math.random() * 540,
      len: 12 + Math.random() * 16,
      spd: 14 + Math.random() * 12,
    }));

    let lastTime = performance.now();
    let frameCount = 0;
    let fps = 60;

    const render = (time) => {
      const dt = Math.min((time - lastTime) / 1000, 0.1);
      lastTime = time;
      frameCount++;
      if (frameCount % 30 === 0) {
        fps = Math.round(1 / dt);
      }

      const W = canvas.width;
      const H = canvas.height;
      const horizon = H * 0.44;

      if (isRunning) {
        // Curve generator
        if (scenario === 'curves') {
          curveAngle = Math.sin(time * 0.0008) * 120;
        } else {
          curveAngle = Math.sin(time * 0.0004) * 45;
        }

        // Scenario handling for lead obstacle
        if (scenario === 'obstacle') {
          obstacleSpeed = 22 + Math.sin(time * 0.001) * 14;
        } else {
          obstacleSpeed = 58 + Math.sin(time * 0.0005) * 8;
        }

        let brakeForce = 0;
        let throttleForce = 0;

        // CHECK MANUAL USER INPUT OVERRIDES FIRST (User Pressed Gas or Brake)
        const isUserBraking = inputRef.current.brake;
        const isUserGassing = inputRef.current.gas;
        const isUserLeft = inputRef.current.left;
        const isUserRight = inputRef.current.right;

        // Manual steering input
        if (isUserLeft) {
          userLateralOffset -= 90 * dt;
          currentSteer = Math.max(-3.5, currentSteer - 6 * dt);
        } else if (isUserRight) {
          userLateralOffset += 90 * dt;
          currentSteer = Math.min(3.5, currentSteer + 6 * dt);
        } else {
          // Auto-center steering gradually if no manual key pressed
          currentSteer += (0 - currentSteer) * 4 * dt;
          userLateralOffset += (0 - userLateralOffset) * 2 * dt;
        }

        // Clamp lateral drift within road boundary
        userLateralOffset = Math.max(-140, Math.min(140, userLateralOffset));

        if (isUserBraking) {
          // USER EMERGENCY BRAKE
          brakeForce = 100;
          throttleForce = 0;
          currentSpeed = Math.max(0, currentSpeed - 75 * dt); // rapid deceleration to stop
        } else if (isUserGassing) {
          // USER GAS / ACCELERATE
          brakeForce = 0;
          throttleForce = 100;
          currentSpeed = Math.min(130, currentSpeed + 28 * dt);
        } else {
          // AUTONOMOUS ACC & LANE CENTERING (or Natural coasting)
          if (drivingMode === 'autonomous') {
            const safeDistance = Math.max(22, (currentSpeed / 10) * 4);

            if (obstacleDistance < safeDistance * 0.6) {
              // AI Emergency Brake
              brakeForce = 100;
              throttleForce = 0;
              currentSpeed = Math.max(12, currentSpeed - 45 * dt);
            } else if (obstacleDistance < safeDistance) {
              // AI Deceleration
              brakeForce = 40;
              throttleForce = 0;
              currentSpeed = Math.max(obstacleSpeed, currentSpeed - 22 * dt);
            } else {
              // AI Accelerate to target speed
              brakeForce = 0;
              if (currentSpeed < targetSpeed) {
                throttleForce = Math.min(80, (targetSpeed - currentSpeed) * 4);
                currentSpeed = Math.min(targetSpeed, currentSpeed + 14 * dt);
              } else {
                throttleForce = 25;
              }
            }

            // AI Lane centering (PID)
            const targetOffset = curveAngle * 0.001;
            if (!isUserLeft && !isUserRight) {
              currentSteer += (targetOffset - currentSteer) * 4 * dt;
            }
          } else {
            // Manual Cruise coasting to target speed
            if (currentSpeed < targetSpeed) {
              currentSpeed += 8 * dt;
              throttleForce = 40;
            } else if (currentSpeed > targetSpeed) {
              currentSpeed -= 8 * dt;
              brakeForce = 15;
            }
          }
        }

        // Update relative obstacle distance
        const relativeSpeedKmh = currentSpeed - obstacleSpeed;
        const relativeSpeedMs = (relativeSpeedKmh * 1000) / 3600;
        obstacleDistance -= relativeSpeedMs * dt;
        if (obstacleDistance < 12) obstacleDistance = 12;
        if (obstacleDistance > 85) obstacleDistance = 85;

        // Road motion
        roadOffset = (roadOffset + (currentSpeed * 1.8 * dt)) % 100;

        // Safety Status determination
        const ttcCalc = relativeSpeedMs > 0.5 ? Math.max(0.5, obstacleDistance / relativeSpeedMs) : 99.9;
        let safety = 'SAFE';
        if (isUserBraking) {
          safety = 'MANUAL BRAKE ACTIVE';
        } else if (obstacleDistance < 22 || ttcCalc < 2.5) {
          safety = 'EMERGENCY BRAKE';
        } else if (obstacleDistance < 36 || ttcCalc < 4.5) {
          safety = 'MAINTAIN GAP';
        }

        setTelemetry({
          speed: Math.round(currentSpeed),
          steeringAngle: Number((currentSteer * 2.5).toFixed(1)),
          laneOffset: Number(((userLateralOffset * 0.01) + (currentSteer * 0.05)).toFixed(2)),
          closestObstacle: Number(obstacleDistance.toFixed(1)),
          ttc: Number(Math.min(99.9, ttcCalc).toFixed(1)),
          leadId: 104,
          leadClass: 'Car',
          leadConf: 94,
          safetyStatus: safety,
          throttle: Math.round(throttleForce),
          brake: Math.round(brakeForce),
          fps,
        });
      }

      // ----------------- DRAW BACKGROUND -----------------
      if (weather === 'night') {
        const nightGrad = ctx.createLinearGradient(0, 0, 0, horizon);
        nightGrad.addColorStop(0, '#040711');
        nightGrad.addColorStop(1, '#0a1020');
        ctx.fillStyle = nightGrad;
        ctx.fillRect(0, 0, W, horizon);

        // Moon
        ctx.fillStyle = '#e2e8f0';
        ctx.beginPath();
        ctx.arc(W * 0.8, horizon * 0.35, 18, 0, Math.PI * 2);
        ctx.fill();
      } else if (weather === 'rain') {
        const rainGrad = ctx.createLinearGradient(0, 0, 0, horizon);
        rainGrad.addColorStop(0, '#111827');
        rainGrad.addColorStop(1, '#1f2937');
        ctx.fillStyle = rainGrad;
        ctx.fillRect(0, 0, W, horizon);
      } else {
        const dayGrad = ctx.createLinearGradient(0, 0, 0, horizon);
        dayGrad.addColorStop(0, '#0284c7');
        dayGrad.addColorStop(0.65, '#38bdf8');
        dayGrad.addColorStop(1, '#93c5fd');
        ctx.fillStyle = dayGrad;
        ctx.fillRect(0, 0, W, horizon);

        // Sun
        ctx.fillStyle = '#fef08a';
        ctx.beginPath();
        ctx.arc(W * 0.75, horizon * 0.4, 26, 0, Math.PI * 2);
        ctx.fill();
      }

      // Distant mountain silhouette
      ctx.fillStyle = weather === 'night' ? '#070b14' : weather === 'rain' ? '#1e293b' : '#334155';
      ctx.beginPath();
      ctx.moveTo(0, horizon);
      for (let x = 0; x <= W; x += 40) {
        const peak = Math.sin((x + curveAngle) * 0.008) * 35 + Math.cos(x * 0.02) * 15;
        ctx.lineTo(x, horizon - 20 - peak);
      }
      ctx.lineTo(W, horizon);
      ctx.closePath();
      ctx.fill();

      // Ground (Roadside terrain)
      ctx.fillStyle = weather === 'night' ? '#060e0a' : weather === 'rain' ? '#142018' : '#1e3a24';
      ctx.fillRect(0, horizon, W, H - horizon);

      // ----------------- DRAW ROAD (PERSPECTIVE 3D) -----------------
      const roadTopW = W * 0.16;
      const roadBottomW = W * 0.78;
      const roadCenterTop = (W / 2) + curveAngle - userLateralOffset * 0.2;
      const roadCenterBottom = (W / 2) - userLateralOffset;

      const roadTL = roadCenterTop - roadTopW / 2;
      const roadTR = roadCenterTop + roadTopW / 2;
      const roadBL = roadCenterBottom - roadBottomW / 2;
      const roadBR = roadCenterBottom + roadBottomW / 2;

      // Asphalt
      ctx.fillStyle = weather === 'night' ? '#131922' : weather === 'rain' ? '#1a2230' : '#273142';
      ctx.beginPath();
      ctx.moveTo(roadTL, horizon);
      ctx.lineTo(roadTR, horizon);
      ctx.lineTo(roadBR, H);
      ctx.lineTo(roadBL, H);
      ctx.closePath();
      ctx.fill();

      // Curbs (Red & White blocks)
      const curbWTop = 6;
      const curbWBottom = 26;
      ctx.fillStyle = '#ef4444';
      ctx.beginPath();
      ctx.moveTo(roadTL - curbWTop, horizon);
      ctx.lineTo(roadTL, horizon);
      ctx.lineTo(roadBL, H);
      ctx.lineTo(roadBL - curbWBottom, H);
      ctx.closePath();
      ctx.fill();

      ctx.beginPath();
      ctx.moveTo(roadTR, horizon);
      ctx.lineTo(roadTR + curbWTop, horizon);
      ctx.lineTo(roadBR + curbWBottom, H);
      ctx.lineTo(roadBR, H);
      ctx.closePath();
      ctx.fill();

      // ----------------- OPENCV LANE DETECTION HIGHLIGHT -----------------
      const egoTopL = roadCenterTop - roadTopW * 0.18;
      const egoTopR = roadCenterTop + roadTopW * 0.18;
      const egoBottomL = roadCenterBottom - roadBottomW * 0.18;
      const egoBottomR = roadCenterBottom + roadBottomW * 0.18;

      ctx.fillStyle = 'rgba(56, 189, 248, 0.18)';
      ctx.beginPath();
      ctx.moveTo(egoTopL, horizon + 2);
      ctx.lineTo(egoTopR, horizon + 2);
      ctx.lineTo(egoBottomR, H);
      ctx.lineTo(egoBottomL, H);
      ctx.closePath();
      ctx.fill();

      // ----------------- LANE MARKINGS -----------------
      const numDashes = 14;
      for (let i = 0; i < numDashes; i++) {
        const p1 = (i / numDashes + roadOffset * 0.01) % 1;
        const p2 = Math.min(1, p1 + 0.04);
        if (p1 >= p2) continue;

        const y1 = horizon + Math.pow(p1, 2.2) * (H - horizon);
        const y2 = horizon + Math.pow(p2, 2.2) * (H - horizon);

        const xOffset1 = (curveAngle - userLateralOffset * 0.2) * (1 - p1) + (roadCenterBottom - W / 2) * p1;
        const xOffset2 = (curveAngle - userLateralOffset * 0.2) * (1 - p2) + (roadCenterBottom - W / 2) * p2;

        const currentRoadW1 = roadTopW + (roadBottomW - roadTopW) * p1;
        const currentRoadW2 = roadTopW + (roadBottomW - roadTopW) * p2;

        const center1 = (W / 2) + xOffset1;
        const center2 = (W / 2) + xOffset2;

        ctx.strokeStyle = '#f8fafc';
        ctx.lineWidth = 1 + p1 * 5;

        // Left lane line
        ctx.beginPath();
        ctx.moveTo(center1 - currentRoadW1 * 0.18, y1);
        ctx.lineTo(center2 - currentRoadW2 * 0.18, y2);
        ctx.stroke();

        // Right lane line
        ctx.beginPath();
        ctx.moveTo(center1 + currentRoadW1 * 0.18, y1);
        ctx.lineTo(center2 + currentRoadW2 * 0.18, y2);
        ctx.stroke();

        // Target path green dotted line
        ctx.strokeStyle = 'rgba(34, 197, 94, 0.55)';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(center1, y1);
        ctx.lineTo(center2, y2);
        ctx.stroke();
      }

      // ----------------- LEAD VEHICLE (WITH YOLO & BYTETRACK OVERLAY) -----------------
      const distNorm = (obstacleDistance - 10) / 75;
      const scale = Math.max(0.18, Math.min(1.0, 1 - Math.pow(distNorm, 0.75)));
      const leadY = horizon + Math.pow(scale, 1.8) * (H - horizon) * 0.88;
      const leadCenterX = roadCenterTop + (roadCenterBottom - roadCenterTop) * scale;

      const carW = 140 * scale;
      const carH = 85 * scale;
      const boxX = leadCenterX - carW / 2;
      const boxY = leadY - carH;

      // Draw Car Model
      ctx.fillStyle = 'rgba(0, 0, 0, 0.45)';
      ctx.beginPath();
      ctx.ellipse(leadCenterX, leadY, carW * 0.6, carH * 0.2, 0, 0, Math.PI * 2);
      ctx.fill();

      // Car body
      ctx.fillStyle = '#3b82f6';
      ctx.beginPath();
      ctx.roundRect(boxX, boxY + carH * 0.35, carW, carH * 0.65, 8 * scale);
      ctx.fill();

      // Cabin / Roof
      ctx.fillStyle = '#1e293b';
      ctx.beginPath();
      ctx.roundRect(boxX + carW * 0.16, boxY + carH * 0.05, carW * 0.68, carH * 0.45, 6 * scale);
      ctx.fill();

      // Taillights
      const isLeadBraking = telemetry.brake > 0 || scenario === 'obstacle' || inputRef.current.brake;
      ctx.fillStyle = isLeadBraking ? '#ff0000' : '#b91c1c';
      if (isLeadBraking) {
        ctx.shadowColor = '#ff2222';
        ctx.shadowBlur = 18;
      }
      ctx.fillRect(boxX + carW * 0.08, boxY + carH * 0.45, carW * 0.18, carH * 0.18);
      ctx.fillRect(boxX + carW * 0.74, boxY + carH * 0.45, carW * 0.18, carH * 0.18);
      ctx.shadowBlur = 0;

      // YOLO Bounding Box
      const boxColor = telemetry.brake > 0 ? '#ef4444' : '#22c55e';
      ctx.strokeStyle = boxColor;
      ctx.lineWidth = 2.5;
      ctx.strokeRect(boxX - 6, boxY - 6, carW + 12, carH + 12);

      // Label Pill
      ctx.fillStyle = boxColor;
      ctx.fillRect(boxX - 6, boxY - 26, Math.max(160, carW + 12), 20);
      ctx.fillStyle = '#050c18';
      ctx.font = 'bold 11px JetBrains Mono, monospace';
      ctx.fillText(`[Car] #${telemetry.leadId} 94% | ${telemetry.closestObstacle}m`, boxX - 2, boxY - 12);

      // Distance tag
      ctx.fillStyle = 'rgba(7, 11, 20, 0.85)';
      ctx.fillRect(boxX - 6, boxY + carH + 10, 135, 18);
      ctx.fillStyle = boxColor;
      ctx.font = '10px JetBrains Mono, monospace';
      ctx.fillText(`TTC: ${telemetry.ttc}s | ${telemetry.safetyStatus}`, boxX - 2, boxY + carH + 23);

      // ----------------- NIGHT / RAIN OVERLAYS -----------------
      if (weather === 'night') {
        const beamGrad = ctx.createRadialGradient(W / 2, H * 0.9, 50, W / 2, horizon + 50, W * 0.5);
        beamGrad.addColorStop(0, 'rgba(254, 240, 138, 0.28)');
        beamGrad.addColorStop(1, 'rgba(254, 240, 138, 0)');
        ctx.fillStyle = beamGrad;
        ctx.beginPath();
        ctx.moveTo(W * 0.2, H);
        ctx.lineTo(roadCenterTop - 120, horizon + 30);
        ctx.lineTo(roadCenterTop + 120, horizon + 30);
        ctx.lineTo(W * 0.8, H);
        ctx.closePath();
        ctx.fill();
      }

      if (weather === 'rain') {
        ctx.strokeStyle = 'rgba(186, 230, 253, 0.35)';
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        for (let drop of rainDrops) {
          drop.y += drop.spd;
          if (drop.y > H) {
            drop.y = 0;
            drop.x = Math.random() * W;
          }
          ctx.moveTo(drop.x, drop.y);
          ctx.lineTo(drop.x + 2, drop.y + drop.len);
        }
        ctx.stroke();
      }

      // ----------------- EGO VEHICLE HOOD HUD (BOTTOM) -----------------
      ctx.fillStyle = '#0b1324';
      ctx.beginPath();
      ctx.moveTo(W * 0.3, H);
      ctx.lineTo(W * 0.5, H - 45);
      ctx.lineTo(W * 0.7, H);
      ctx.closePath();
      ctx.fill();
      ctx.strokeStyle = '#1d2a45';
      ctx.lineWidth = 2;
      ctx.stroke();

      // Optical Camera Crosshair in Center
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.75)';
      ctx.lineWidth = 1.5;
      const chX = W / 2;
      const chY = H - 55;
      ctx.beginPath();
      ctx.moveTo(chX - 16, chY);
      ctx.lineTo(chX + 16, chY);
      ctx.moveTo(chX, chY - 16);
      ctx.lineTo(chX, chY + 16);
      ctx.stroke();

      // Trajectory vector line
      ctx.strokeStyle = telemetry.brake > 0 ? '#ef4444' : '#22c55e';
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(W / 2, H - 20);
      ctx.lineTo((W / 2) + telemetry.steeringAngle * 18, H - 90);
      ctx.stroke();

      // Top Alert Banner if Braking
      if (inputRef.current.brake) {
        ctx.fillStyle = 'rgba(239, 68, 68, 0.95)';
        ctx.fillRect(W * 0.24, 16, W * 0.52, 42);
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 16px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('🛑 MANUAL BRAKE APPLIED — VEHICLE STOPPING', W / 2, 42);
        ctx.textAlign = 'left';
      } else if (telemetry.safetyStatus === 'EMERGENCY BRAKE') {
        ctx.fillStyle = 'rgba(239, 68, 68, 0.88)';
        ctx.fillRect(W * 0.24, 16, W * 0.52, 42);
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 15px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('⚠️ COLLISION WARNING — AUTOMATIC EMERGENCY BRAKING ACTIVE', W / 2, 42);
        ctx.textAlign = 'left';
      }

      animationFrameId = requestAnimationFrame(render);
    };

    animationFrameId = requestAnimationFrame(render);

    return () => cancelAnimationFrame(animationFrameId);
  }, [isRunning, drivingMode, targetSpeed, weather, scenario]);

  return (
    <div>
      <PageHeader
        title="Autonomous Driving Simulation"
        subtitle="Live vehicle control & perception: control throttle, steering, and emergency braking manually or let AI drive"
      />

      {/* SIMULATOR CANVAS VIEWPORT */}
      <div className="card" style={{ overflow: 'hidden', marginBottom: '22px' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '12px 20px',
            background: '#0c1426',
            borderBottom: '1px solid #1a2846',
            flexWrap: 'wrap',
            gap: '10px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap' }}>
            <span className="status-pill pill-online">
              <span className="pill-dot" aria-hidden="true" />
              SIMULATION {isRunning ? 'RUNNING' : 'PAUSED'}
            </span>
            <span className="chip chip-get">FPS: {telemetry.fps}</span>
            <span className="chip" style={{ background: 'rgba(56, 189, 248, 0.12)', color: '#38bdf8' }}>
              Mode: {drivingMode === 'autonomous' ? 'AI Autonomous Cruise (ACC)' : 'Manual Driver Control'}
            </span>
          </div>

          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => setIsRunning(!isRunning)}
              style={{ padding: '6px 14px', fontSize: '13px' }}
            >
              {isRunning ? '⏸️ Pause' : '▶️ Resume'}
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => {
                setTargetSpeed(70);
                setScenario('highway');
              }}
              style={{ padding: '6px 14px', fontSize: '13px' }}
            >
              ↺ Reset
            </button>
          </div>
        </div>

        {/* 16:9 Aspect Ratio Canvas */}
        <div style={{ position: 'relative', width: '100%', background: '#070c17', display: 'flex', justifyContent: 'center' }}>
          <canvas
            ref={canvasRef}
            width={960}
            height={540}
            style={{ width: '100%', maxHeight: '540px', objectFit: 'contain', display: 'block' }}
          />

          {/* HUD OVERLAY TELEMETRY WIDGET */}
          <div
            style={{
              position: 'absolute',
              top: '16px',
              left: '16px',
              background: 'rgba(7, 12, 23, 0.85)',
              backdropFilter: 'blur(8px)',
              padding: '12px 16px',
              borderRadius: '10px',
              border: '1px solid rgba(59, 130, 246, 0.3)',
              minWidth: '220px',
              pointerEvents: 'none',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
              <span style={{ fontSize: '11px', color: '#94a3b8' }}>SPEED</span>
              <span style={{ fontSize: '11px', color: '#94a3b8' }}>STEER</span>
              <span style={{ fontSize: '11px', color: '#94a3b8' }}>STATUS</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <span className="mono" style={{ fontSize: '24px', fontWeight: 'bold', color: '#38bdf8' }}>
                {telemetry.speed} <small style={{ fontSize: '12px', color: '#94a3b8' }}>km/h</small>
              </span>
              <span className="mono" style={{ fontSize: '16px', color: '#a78bfa' }}>
                {telemetry.steeringAngle > 0 ? `+${telemetry.steeringAngle}` : telemetry.steeringAngle}°
              </span>
              <span
                className="chip"
                style={{
                  background:
                    telemetry.brake > 0
                      ? 'rgba(239, 68, 68, 0.3)'
                      : telemetry.safetyStatus === 'SAFE'
                      ? 'rgba(34, 197, 94, 0.2)'
                      : 'rgba(245, 158, 11, 0.2)',
                  color:
                    telemetry.brake > 0
                      ? '#f87171'
                      : telemetry.safetyStatus === 'SAFE'
                      ? '#4ade80'
                      : '#fde047',
                  fontWeight: 'bold',
                  fontSize: '11px',
                }}
              >
                {telemetry.brake > 0 ? 'BRAKING' : telemetry.safetyStatus}
              </span>
            </div>
          </div>
        </div>

        {/* INTERACTIVE PEDALS & DRIVER CONTROLS (DIRECT ON-SCREEN BUTTONS + KEYBOARD SHORTCUTS) */}
        <div
          style={{
            padding: '16px 20px',
            background: 'rgba(10, 16, 29, 0.95)',
            borderTop: '1px solid #1a2846',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
            <span style={{ fontSize: '13px', color: '#cbd5e1' }}>
              🎮 <strong>Driver Controls:</strong> Click & hold pedals below, or press keys on your keyboard:
            </span>
            <div style={{ display: 'flex', gap: '10px', fontSize: '12px', color: '#94a3b8' }}>
              <span><kbd style={{ background: '#1e293b', padding: '2px 6px', borderRadius: '4px', border: '1px solid #334155' }}>Space</kbd> or <kbd style={{ background: '#1e293b', padding: '2px 6px', borderRadius: '4px', border: '1px solid #334155' }}>S</kbd> = Brake</span>
              <span><kbd style={{ background: '#1e293b', padding: '2px 6px', borderRadius: '4px', border: '1px solid #334155' }}>W</kbd> / <kbd style={{ background: '#1e293b', padding: '2px 6px', borderRadius: '4px', border: '1px solid #334155' }}>↑</kbd> = Gas</span>
              <span><kbd style={{ background: '#1e293b', padding: '2px 6px', borderRadius: '4px', border: '1px solid #334155' }}>A</kbd> / <kbd style={{ background: '#1e293b', padding: '2px 6px', borderRadius: '4px', border: '1px solid #334155' }}>D</kbd> = Steer</span>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '12px' }}>
            {/* BIG RED EMERGENCY BRAKE PEDAL */}
            <button
              type="button"
              className="btn"
              style={{
                background: activePedal.brake || inputRef.current.brake ? '#dc2626' : 'rgba(239, 68, 68, 0.15)',
                color: activePedal.brake || inputRef.current.brake ? '#ffffff' : '#fca5a5',
                border: '2px solid #ef4444',
                padding: '14px 18px',
                fontSize: '15px',
                fontWeight: 'bold',
                borderRadius: '12px',
                boxShadow: activePedal.brake || inputRef.current.brake ? '0 0 20px rgba(239, 68, 68, 0.6)' : 'none',
                cursor: 'pointer',
                transition: 'all 0.1s ease',
              }}
              onMouseDown={() => {
                inputRef.current.brake = true;
                setActivePedal((p) => ({ ...p, brake: true }));
              }}
              onMouseUp={() => {
                inputRef.current.brake = false;
                setActivePedal((p) => ({ ...p, brake: false }));
              }}
              onTouchStart={() => {
                inputRef.current.brake = true;
                setActivePedal((p) => ({ ...p, brake: true }));
              }}
              onTouchEnd={() => {
                inputRef.current.brake = false;
                setActivePedal((p) => ({ ...p, brake: false }));
              }}
            >
              🛑 HOLD TO BRAKE
            </button>

            {/* GREEN ACCELERATOR / GAS PEDAL */}
            <button
              type="button"
              className="btn"
              style={{
                background: activePedal.gas || inputRef.current.gas ? '#16a34a' : 'rgba(34, 197, 94, 0.15)',
                color: activePedal.gas || inputRef.current.gas ? '#ffffff' : '#86efac',
                border: '2px solid #22c55e',
                padding: '14px 18px',
                fontSize: '15px',
                fontWeight: 'bold',
                borderRadius: '12px',
                boxShadow: activePedal.gas || inputRef.current.gas ? '0 0 20px rgba(34, 197, 94, 0.6)' : 'none',
                cursor: 'pointer',
                transition: 'all 0.1s ease',
              }}
              onMouseDown={() => {
                inputRef.current.gas = true;
                setActivePedal((p) => ({ ...p, gas: true }));
              }}
              onMouseUp={() => {
                inputRef.current.gas = false;
                setActivePedal((p) => ({ ...p, gas: false }));
              }}
              onTouchStart={() => {
                inputRef.current.gas = true;
                setActivePedal((p) => ({ ...p, gas: true }));
              }}
              onTouchEnd={() => {
                inputRef.current.gas = false;
                setActivePedal((p) => ({ ...p, gas: false }));
              }}
            >
              ⚡ HOLD GAS (ACCELERATE)
            </button>

            {/* STEER LEFT */}
            <button
              type="button"
              className="btn btn-ghost"
              style={{ padding: '14px', fontSize: '14px', fontWeight: '600' }}
              onMouseDown={() => { inputRef.current.left = true; }}
              onMouseUp={() => { inputRef.current.left = false; }}
              onTouchStart={() => { inputRef.current.left = true; }}
              onTouchEnd={() => { inputRef.current.left = false; }}
            >
              ◀ Steer Left (A)
            </button>

            {/* STEER RIGHT */}
            <button
              type="button"
              className="btn btn-ghost"
              style={{ padding: '14px', fontSize: '14px', fontWeight: '600' }}
              onMouseDown={() => { inputRef.current.right = true; }}
              onMouseUp={() => { inputRef.current.right = false; }}
              onTouchStart={() => { inputRef.current.right = true; }}
              onTouchEnd={() => { inputRef.current.right = false; }}
            >
              Steer Right (D) ▶
            </button>
          </div>
        </div>
      </div>

      {/* SIMULATION CONFIGURATION & STRESS TESTING */}
      <div className="grid grid-3" style={{ marginBottom: '22px' }}>
        {/* Driving Mode & Speed */}
        <div className="card pad">
          <h3 style={{ margin: '0 0 12px 0', fontSize: '15px' }}>🤖 Autopilot Mode</h3>
          <div style={{ display: 'flex', gap: '8px', marginBottom: '14px' }}>
            <button
              type="button"
              className={`btn ${drivingMode === 'autonomous' ? 'btn-primary' : 'btn-ghost'}`}
              style={{ flex: 1, fontSize: '13px', padding: '8px 12px' }}
              onClick={() => setDrivingMode('autonomous')}
            >
              🤖 Autonomous (AI)
            </button>
            <button
              type="button"
              className={`btn ${drivingMode === 'manual' ? 'btn-primary' : 'btn-ghost'}`}
              style={{ flex: 1, fontSize: '13px', padding: '8px 12px' }}
              onClick={() => setDrivingMode('manual')}
            >
              🕹️ Manual Only
            </button>
          </div>

          <label className="field">
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>Target Cruise Speed</span>
              <strong className="mono">{targetSpeed} km/h</strong>
            </div>
            <input
              type="range"
              min="30"
              max="120"
              value={targetSpeed}
              onChange={(e) => setTargetSpeed(Number(e.target.value))}
            />
          </label>
        </div>

        {/* Test Scenarios */}
        <div className="card pad">
          <h3 style={{ margin: '0 0 12px 0', fontSize: '15px' }}>🛣️ Test Scenario</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <button
              type="button"
              className={`btn ${scenario === 'highway' ? 'btn-primary' : 'btn-ghost'}`}
              style={{ fontSize: '12px', textAlign: 'left', padding: '8px 12px' }}
              onClick={() => setScenario('highway')}
            >
              🚗 Highway Cruise & Lane Centering
            </button>
            <button
              type="button"
              className={`btn ${scenario === 'obstacle' ? 'btn-primary' : 'btn-ghost'}`}
              style={{ fontSize: '12px', textAlign: 'left', padding: '8px 12px' }}
              onClick={() => setScenario('obstacle')}
            >
              ⚠️ Lead Vehicle Sudden Brake
            </button>
            <button
              type="button"
              className={`btn ${scenario === 'curves' ? 'btn-primary' : 'btn-ghost'}`}
              style={{ fontSize: '12px', textAlign: 'left', padding: '8px 12px' }}
              onClick={() => setScenario('curves')}
            >
              🌀 High-Curvature Mountain Road
            </button>
          </div>
        </div>

        {/* Weather & Lighting */}
        <div className="card pad">
          <h3 style={{ margin: '0 0 12px 0', fontSize: '15px' }}>🌤️ Environment & Weather</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <button
              type="button"
              className={`btn ${weather === 'day' ? 'btn-primary' : 'btn-ghost'}`}
              style={{ fontSize: '12px', textAlign: 'left', padding: '8px 12px' }}
              onClick={() => setWeather('day')}
            >
              ☀️ Clear Daylight
            </button>
            <button
              type="button"
              className={`btn ${weather === 'night' ? 'btn-primary' : 'btn-ghost'}`}
              style={{ fontSize: '12px', textAlign: 'left', padding: '8px 12px' }}
              onClick={() => setWeather('night')}
            >
              🌙 Night Driving (Headlights)
            </button>
            <button
              type="button"
              className={`btn ${weather === 'rain' ? 'btn-primary' : 'btn-ghost'}`}
              style={{ fontSize: '12px', textAlign: 'left', padding: '8px 12px' }}
              onClick={() => setWeather('rain')}
            >
              🌧️ Heavy Rain & Wet Asphalt
            </button>
          </div>
        </div>
      </div>

      {/* LIVE TELEMETRY BREAKDOWN */}
      <div className="card pad">
        <h3 style={{ margin: '0 0 14px 0', fontSize: '15px' }}>📊 Live ADAS Perception & Vehicle Telemetry</h3>
        <div className="kv-grid">
          <div className="kv">
            <span>Current Velocity</span>
            <strong className="mono" style={{ color: '#38bdf8' }}>{telemetry.speed} km/h</strong>
          </div>
          <div className="kv">
            <span>Steering Angle (PID)</span>
            <strong className="mono">{telemetry.steeringAngle > 0 ? `+${telemetry.steeringAngle}` : telemetry.steeringAngle}°</strong>
          </div>
          <div className="kv">
            <span>Lane Center Offset</span>
            <strong className="mono">{telemetry.laneOffset} m</strong>
          </div>
          <div className="kv">
            <span>Closest Obstacle</span>
            <strong className="mono" style={{ color: telemetry.closestObstacle < 25 ? '#ef4444' : '#22c55e' }}>
              {telemetry.closestObstacle} m ({telemetry.leadClass})
            </strong>
          </div>
          <div className="kv">
            <span>Time-to-Collision (TTC)</span>
            <strong className="mono">{telemetry.ttc} s</strong>
          </div>
          <div className="kv">
            <span>Brake Pressure</span>
            <strong className="mono" style={{ color: telemetry.brake > 0 ? '#ef4444' : '#94a3b8' }}>
              {telemetry.brake}% {telemetry.brake > 0 ? '🔴 ENGAGED' : ''}
            </strong>
          </div>
          <div className="kv">
            <span>Throttle Torque</span>
            <strong className="mono">{telemetry.throttle}%</strong>
          </div>
          <div className="kv">
            <span>Safety System</span>
            <strong className="mono" style={{ color: telemetry.brake > 0 ? '#ef4444' : '#22c55e' }}>
              {telemetry.brake > 0 ? 'BRAKING' : telemetry.safetyStatus}
            </strong>
          </div>
        </div>
      </div>
    </div>
  );
}
