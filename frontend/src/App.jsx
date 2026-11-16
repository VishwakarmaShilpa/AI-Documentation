import { useState, useRef, useEffect, useCallback  } from "react";
import "./App.css";

const API = "http://127.0.0.1:8000";

function errorText(data, fallback) {
  return data && typeof data.detail === "string" ? data.detail : fallback;
}

function AuthForm({ onToken }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      let res;
      if (mode === "signup") {
        res = await fetch(`${API}/auth/signup`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });
      } else {
        res = await fetch(`${API}/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: new URLSearchParams({ username: email, password }),
        });
      }
      const data = await res.json();
      if (!res.ok) throw new Error(errorText(data, "Something went wrong"));
      onToken(data.access_token);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <form className="auth" onSubmit={submit}>
      <h1>{mode === "login" ? "Log in" : "Create account"}</h1>
      <input
        type="email"
        placeholder="Email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        required
      />
      <input
        type="password"
        placeholder="Password (8+ characters)"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
      />
      {error && <p className="error">{error}</p>}
      <button className="primary" disabled={loading}>
        {loading ? "Please wait..." : mode === "login" ? "Log in" : "Sign up"}
      </button>
      <p className="switch">
        {mode === "login" ? "No account? " : "Already have an account? "}
        <button
          type="button"
          className="link"
          onClick={() => {
            setMode(mode === "login" ? "signup" : "login");
            setError("");
          }}
        >
          {mode === "login" ? "Sign up" : "Log in"}
        </button>
      </p>
    </form>
  );
}

function Chat({ token, onLogout }) {
  const [docs, setDocs] = useState([]);
  const [docId, setDocId] = useState("");
  const [uploading, setUploading] = useState(false);
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef(null);

  const authFetch = useCallback(
    async (path, options = {}) => {
      const res = await fetch(`${API}${path}`, {
        ...options,
        headers: { ...(options.headers || {}), Authorization: `Bearer ${token}` },
      });
      if (res.status === 401) {
        onLogout();
        throw new Error("Session expired. Please log in again.");
      }
      return res;
    },
    [token, onLogout]
  );

  useEffect(() => {
    (async () => {
      try {
        const res = await authFetch("/documents");
        const data = await res.json();
        if (res.ok) {
          setDocs(data);
          if (data.length) setDocId(data[0].doc_id);
        }
      } catch (err) {
        setError(err.message);
      }
    })();
  }, [authFetch]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, asking]);

  async function handleUpload(e) {
    const file = e.target.files[0];
    if (!file) return;
    setError("");
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await authFetch("/upload", { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok) throw new Error(errorText(data, "Upload failed"));
      setDocs((d) => [{ doc_id: data.doc_id, filename: data.filename }, ...d]);
      setDocId(data.doc_id);
      setMessages([]);
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  async function handleAsk(e) {
    e.preventDefault();
    const q = question.trim();
    if (!q || !docId) return;
    setQuestion("");
    setError("");
    setMessages((m) => [...m, { role: "user", text: q }]);
    setAsking(true);
    try {
      const res = await authFetch("/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ doc_id: docId, question: q }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(errorText(data, "Request failed"));
      setMessages((m) => [
        ...m,
        { role: "bot", text: data.answer, sources: data.sources },
      ]);
    } catch (err) {
      setError(err.message);
    } finally {
      setAsking(false);
    }
  }

  return (
    <div className="app">
      <div className="topbar">
        <h1>Document Q&amp;A</h1>
        <button className="logout" onClick={onLogout}>Log out</button>
      </div>

      <div className="upload">
        <label className="upload-btn">
          {uploading ? "Processing..." : "Upload a PDF"}
          <input
            type="file"
            accept="application/pdf"
            onChange={handleUpload}
            disabled={uploading}
            hidden
          />
        </label>
        {docs.length > 0 ? (
          <select
            value={docId}
            onChange={(e) => {
              setDocId(e.target.value);
              setMessages([]);
            }}
          >
            {docs.map((d) => (
              <option key={d.doc_id} value={d.doc_id}>
                {d.filename}
              </option>
            ))}
          </select>
        ) : (
          <span className="filename">No documents yet</span>
        )}
      </div>

      <div className="chat">
        {messages.length === 0 && (
          <p className="hint">
            {docId
              ? "Ask a question about your document."
              : "Upload a PDF to get started."}
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            <p>{m.text}</p>
            {m.sources && m.sources.length > 0 && (
              <details>
                <summary>Sources ({m.sources.length})</summary>
                {m.sources.map((s) => (
                  <blockquote key={s.chunk_index}>
                    <small>Match score: {s.score}</small>
                    <br />
                    {s.text}
                  </blockquote>
                ))}
              </details>
            )}
          </div>
        ))}
        {asking && <div className="msg bot">Thinking...</div>}
        <div ref={bottomRef} />
      </div>

      {error && <p className="error">{error}</p>}

      <form onSubmit={handleAsk} className="ask">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask about your document..."
          disabled={!docId || asking}
        />
        <button disabled={!docId || asking || !question.trim()}>Ask</button>
      </form>
    </div>
  );
}

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem("token"));

  function saveToken(t) {
    localStorage.setItem("token", t);
    setToken(t);
  }

  const logout = useCallback(() => {
    localStorage.removeItem("token");
    setToken(null);
  }, []);

  if (!token) return <AuthForm onToken={saveToken} />;
  return <Chat token={token} onLogout={logout} />;
}