import { useState } from 'react';

function App() {
  const [message, setMessage] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);

  const handleClick = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/hello');
      const data = await response.json();
      setMessage(JSON.stringify(data, null, 2));
    } catch (error) {
      setMessage(`Error: ${error}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: '20px', fontFamily: 'sans-serif' }}>
      <h1>LeRoPilot Frontend</h1>
      <button
        onClick={handleClick}
        disabled={loading}
        style={{
          padding: '10px 20px',
          fontSize: '16px',
          cursor: loading ? 'not-allowed' : 'pointer',
        }}
        data-testid="test-button"
      >
        {loading ? 'Loading...' : 'Test Backend API'}
      </button>
      {message && (
        <pre
          style={{
            marginTop: '20px',
            padding: '10px',
            background: '#f5f5f5',
            border: '1px solid #ddd',
            borderRadius: '4px',
          }}
        >
          {message}
        </pre>
      )}
    </div>
  );
}

export default App;
