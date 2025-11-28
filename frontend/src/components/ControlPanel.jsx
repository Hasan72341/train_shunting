import { useState } from 'react';

function ControlPanel({ onStop, onForward, onReverse }) {
  const [status, setStatus] = useState(null);

  async function handle(action, fn) {
    try {
      setStatus(`Running ${action}...`);
      await fn();
      setStatus(`${action} command sent.`);
    } catch (error) {
      setStatus(`Error: ${error.message}`);
    }
  }

  return (
    <section>
      <h2>Manual Overrides</h2>
      <div style={{ display: 'flex', gap: '1rem' }}>
        <button onClick={() => handle('Stop', onStop)}>Stop</button>
        <button onClick={() => handle('Forward', onForward)}>Forward</button>
        <button onClick={() => handle('Reverse', onReverse)}>Reverse</button>
      </div>
      {status && <p>{status}</p>}
    </section>
  );
}

export default ControlPanel;
