import ReactDOM from 'react-dom/client';
import App from './App';
import './styles.css';

// React StrictMode intentionally double-mounts effects in development. The
// React Three Fiber Canvas owns an internal renderer root; that dev-only
// teardown/remount sequence can trigger React 19's nested-root unmount warning.
// The app has explicit effect cleanup, so mount the dashboard once.
const container = document.getElementById('root');
if (!container) throw new Error('JARVIS root element was not found.');
ReactDOM.createRoot(container).render(<App />);
