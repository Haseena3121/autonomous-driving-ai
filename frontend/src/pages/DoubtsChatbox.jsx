import { useEffect, useRef, useState } from 'react';
import { api } from '../services/api.js';
import PageHeader from '../components/PageHeader.jsx';

const SUGGESTIONS = [
  'How do I train YOLOv8 on Google Colab for BDD100K?',
  'Where do I put best.pt and how do I reload it?',
  'How does the OpenCV lane detection algorithm work?',
  'How does ByteTrack track objects across video frames?',
  'Why is MiDaS depth relative and not in metres?',
  'How do I connect the simulator to CARLA?',
  'How can I enable CUDA GPU acceleration?',
  'Where can I read the project and model documentation in file format?',
];

const INITIAL_MESSAGE = {
  id: 'init-1',
  role: 'assistant',
  content: `### 👋 Hello! I am your Autonomous Driving & Project AI Assistant.

I can help resolve doubts, explain algorithms, and guide you through:
* **Model Training:** Training YOLOv8 on BDD100K with Google Colab and placing \`best.pt\`.
* **Computer Vision:** Bounding box detection, ByteTrack tracking, and trajectory history.
* **OpenCV Lane Detection:** Canny edge, Hough lines, ROI masking, and steering offset math.
* **Monocular Depth:** MiDaS relative depth maps vs metric LiDAR.
* **CARLA & ROS 2:** Simulator bridges, vehicle spawning, and perception topics.
* **Documentation & Setup:** All docs are saved in \`docs/PROJECT_DOCUMENTATION.md\` and \`docs/MODEL_INFORMATION.md\`.

Click any suggested question below or type your doubt!`,
  category: 'General',
  time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
};

function renderMarkdown(text) {
  if (!text) return null;

  // Split text by lines
  const lines = text.split('\n');
  const elements = [];
  let inCodeBlock = false;
  let codeBuffer = [];
  let listBuffer = [];

  const flushList = () => {
    if (listBuffer.length > 0) {
      elements.push(
        <ul key={`ul-${elements.length}`} style={{ paddingLeft: '22px', margin: '8px 0' }}>
          {listBuffer.map((item, idx) => (
            <li key={idx} style={{ margin: '4px 0' }}>{renderInline(item)}</li>
          ))}
        </ul>
      );
      listBuffer = [];
    }
  };

  const renderInline = (str) => {
    // Basic bold and inline code parser
    const parts = [];
    let remaining = str;
    let keyIdx = 0;

    // Pattern: `code` or **bold** or *italic*
    const regex = /(\*\*.*?\*\*|`.*?`|\*.*?\*)/g;
    const splitParts = remaining.split(regex);

    for (let part of splitParts) {
      if (part.startsWith('**') && part.endsWith('**')) {
        parts.push(<strong key={keyIdx++}>{part.slice(2, -2)}</strong>);
      } else if (part.startsWith('`') && part.endsWith('`')) {
        parts.push(
          <code key={keyIdx++} className="mono" style={{ background: 'rgba(59, 130, 246, 0.15)', padding: '2px 6px', borderRadius: '4px', fontSize: '0.9em', color: '#93c5fd' }}>
            {part.slice(1, -1)}
          </code>
        );
      } else if (part.startsWith('*') && part.endsWith('*')) {
        parts.push(<em key={keyIdx++}>{part.slice(1, -1)}</em>);
      } else if (part) {
        parts.push(part);
      }
    }
    return parts;
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (line.startsWith('```')) {
      if (inCodeBlock) {
        // end code block
        elements.push(
          <pre key={`code-${elements.length}`} className="code-block" style={{ margin: '10px 0', overflowX: 'auto', padding: '12px', borderRadius: '8px', background: '#090e1a', border: '1px solid #1a2742' }}>
            <code className="mono" style={{ fontSize: '13px' }}>{codeBuffer.join('\n')}</code>
          </pre>
        );
        codeBuffer = [];
        inCodeBlock = false;
      } else {
        flushList();
        inCodeBlock = true;
      }
      continue;
    }

    if (inCodeBlock) {
      codeBuffer.push(line);
      continue;
    }

    if (line.startsWith('### ')) {
      flushList();
      elements.push(
        <h4 key={`h-${elements.length}`} style={{ margin: '12px 0 6px', color: '#60a5fa', fontSize: '16px' }}>
          {line.replace('### ', '')}
        </h4>
      );
    } else if (line.startsWith('* ') || line.startsWith('- ')) {
      listBuffer.push(line.slice(2));
    } else if (/^\d+\.\s/.test(line)) {
      listBuffer.push(line.replace(/^\d+\.\s/, ''));
    } else if (line.trim() === '') {
      flushList();
    } else {
      flushList();
      elements.push(
        <p key={`p-${elements.length}`} style={{ margin: '6px 0' }}>
          {renderInline(line)}
        </p>
      );
    }
  }

  flushList();
  if (codeBuffer.length > 0) {
    elements.push(
      <pre key={`code-${elements.length}`} className="code-block" style={{ margin: '10px 0', overflowX: 'auto', padding: '12px', borderRadius: '8px', background: '#090e1a', border: '1px solid #1a2742' }}>
        <code className="mono" style={{ fontSize: '13px' }}>{codeBuffer.join('\n')}</code>
      </pre>
    );
  }

  return elements;
}

export default function DoubtsChatbox() {
  const [messages, setMessages] = useState(() => {
    const saved = sessionStorage.getItem('adas_doubts_chat');
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch {
        /* ignore */
      }
    }
    return [INITIAL_MESSAGE];
  });
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    sessionStorage.setItem('adas_doubts_chat', JSON.stringify(messages));
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async (textToSend) => {
    const query = (textToSend || input).trim();
    if (!query || loading) return;

    const userMsg = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: query,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const history = messages.slice(-4).map((m) => ({ role: m.role, content: m.content }));
      const res = await api.sendChatMessage(query, history);
      const assistantMsg = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: res.reply || 'I am ready to help. Please ask any doubt about the models, pipelines, or code.',
        category: res.category || 'General',
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      const errorMsg = {
        id: `err-${Date.now()}`,
        role: 'assistant',
        content: `**Error:** Unable to connect to the doubts assistant backend. ${err.message || 'Please check that Flask server is running.'}`,
        category: 'Error',
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const clearChat = () => {
    setMessages([INITIAL_MESSAGE]);
    sessionStorage.removeItem('adas_doubts_chat');
  };

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto' }}>
      <PageHeader
        title="Doubts Assistant"
        subtitle="Ask any question about model training, YOLO detection, ByteTrack, OpenCV lane detection, MiDaS depth, or CARLA simulation"
      >
        <button type="button" className="btn btn-ghost" onClick={clearChat} style={{ fontSize: '13px' }}>
          🗑️ Clear chat
        </button>
      </PageHeader>

      <div className="card chat-container">
        <div className="chat-header">
          <div className="chat-header-info">
            <span className="chat-bot-avatar">🤖</span>
            <div>
              <strong style={{ display: 'block', fontSize: '15px' }}>ADAS Doubts & AI Expert</strong>
              <span className="muted" style={{ fontSize: '12px' }}>Trained on BDD100K, YOLOv8, ByteTrack, OpenCV, MiDaS & CARLA</span>
            </div>
          </div>
          <span className="status-pill pill-online" style={{ fontSize: '12px' }}>
            <span className="pill-dot" aria-hidden="true" />
            Assistant ready
          </span>
        </div>

        {/* Suggested questions */}
        <div className="chat-suggestions-bar">
          <span className="muted" style={{ fontSize: '12px', whiteSpace: 'nowrap', marginRight: '6px' }}>Suggested:</span>
          <div className="chat-suggestions-scroll">
            {SUGGESTIONS.map((s, idx) => (
              <button
                key={idx}
                type="button"
                className="chat-suggestion-chip"
                onClick={() => handleSend(s)}
                disabled={loading}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        {/* Message timeline */}
        <div className="chat-messages">
          {messages.map((m) => (
            <div key={m.id} className={`chat-bubble-wrap ${m.role}`}>
              <div className="chat-bubble-meta">
                <span className="chat-bubble-role">{m.role === 'user' ? 'You' : 'ADAS Assistant'}</span>
                {m.category && m.role === 'assistant' ? (
                  <span className="chip" style={{ fontSize: '10px', padding: '1px 6px' }}>{m.category}</span>
                ) : null}
                <span className="chat-bubble-time">{m.time}</span>
              </div>
              <div className={`chat-bubble ${m.role}`}>
                {renderMarkdown(m.content)}
              </div>
            </div>
          ))}

          {loading ? (
            <div className="chat-bubble-wrap assistant">
              <div className="chat-bubble-meta">
                <span className="chat-bubble-role">ADAS Assistant</span>
                <span className="chat-bubble-time">Thinking...</span>
              </div>
              <div className="chat-bubble assistant typing">
                <span className="typing-dot" />
                <span className="typing-dot" />
                <span className="typing-dot" />
              </div>
            </div>
          ) : null}

          <div ref={messagesEndRef} />
        </div>

        {/* Input box */}
        <div className="chat-input-bar">
          <input
            type="text"
            className="input chat-input"
            placeholder="Type your question or doubt here (e.g., 'How do I train best.pt in Colab?') and press Enter..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
          />
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => handleSend()}
            disabled={!input.trim() || loading}
            style={{ padding: '0 20px', minWidth: '90px' }}
          >
            {loading ? 'Sending...' : 'Send ➔'}
          </button>
        </div>
      </div>
    </div>
  );
}
