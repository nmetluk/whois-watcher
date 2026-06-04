import React from 'react';
import { createRoot } from 'react-dom/client';
// Самохостящиеся шрифты (CSP style-src/font-src 'self', без Google Fonts)
import '@fontsource/pt-sans/400.css';
import '@fontsource/pt-sans/700.css';
import '@fontsource/pt-sans/400-italic.css';
import '@fontsource/pt-sans/700-italic.css';
import 'material-symbols/rounded.css';
import './styles/index.css';
import App from './App.tsx';

createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>);
