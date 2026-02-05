import { useMemo, useState } from "react";
import "./App.css";

export default function App() {
  const [count, setCount] = useState(0);
  const doubled = useMemo(() => count * 2, [count]);

  return (
    <div className="app">
      <header className="card">
        <h1>Vibe Skilling</h1>
        <p className="muted">React + Vite + TypeScript</p>
      </header>

      <main className="card">
        <div className="row">
          <button type="button" onClick={() => setCount((c) => c - 1)}>
            -
          </button>
          <div className="counter">
            <div className="count">{count}</div>
            <div className="muted">doubled: {doubled}</div>
          </div>
          <button type="button" onClick={() => setCount((c) => c + 1)}>
            +
          </button>
        </div>
      </main>
    </div>
  );
}

