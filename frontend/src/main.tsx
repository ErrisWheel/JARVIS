import ReactDOM from 'react-dom/client';
import App from './App';
import './styles.css';

// Mount one React root. The hologram owns a Three.js WebGL renderer directly
// inside an effect; it does not create a nested React root, so renderer cleanup
// cannot synchronously unmount React Three Fiber while React is rendering.
const container = document.getElementById('root');
if (!container) throw new Error('JARVIS root element was not found.');
ReactDOM.createRoot(container).render(<App />);
