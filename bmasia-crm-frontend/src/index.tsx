import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import { AuthProvider } from './contexts/AuthContext';
import { ThemeProvider } from './contexts/ThemeContext';
import SessionTimeout from './components/SessionTimeout';

// Log environment at app startup
console.log('🔧 === APP STARTUP DEBUG ===');
console.log('REACT_APP_API_URL:', process.env.REACT_APP_API_URL);
console.log('REACT_APP_BYPASS_AUTH:', process.env.REACT_APP_BYPASS_AUTH);
console.log('NODE_ENV:', process.env.NODE_ENV);
console.log('Window location:', window.location.href);
console.log('============================');

const root = ReactDOM.createRoot(
  document.getElementById('root') as HTMLElement
);

// Debug function to test API directly from browser console
(window as any).debugAPI = async () => {
  console.log('=== DEBUG API TEST ===');
  console.log('Testing direct fetch to backend...');
  console.log('URL: https://bmasia-crm.onrender.com/api/v1/companies/?page=1&page_size=25');

  try {
    const response = await fetch('https://bmasia-crm.onrender.com/api/v1/companies/?page=1&page_size=25', {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        // No Authorization header - testing without auth
      },
    });

    console.log('Response Status:', response.status);
    console.log('Response OK:', response.ok);
    console.log('Response Headers:', Object.fromEntries(response.headers.entries()));

    const data = await response.json();
    console.log('Response Data:', data);
    console.log('Count:', data.count);
    console.log('Results Length:', data.results?.length);

    if (data.results && data.results.length > 0) {
      console.log('First Company:', data.results[0]);
    } else {
      console.warn('WARNING: No results returned!');
    }

    return data;
  } catch (error) {
    console.error('Fetch Error:', error);
    return null;
  }
};

console.log('💡 Debug function available: Run debugAPI() in console to test API directly');

root.render(
  <React.StrictMode>
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <App />
          <SessionTimeout />
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  </React.StrictMode>
);