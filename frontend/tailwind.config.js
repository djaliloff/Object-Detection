/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#0a0a0a',
        surface: '#121212',
        border: '#1f1f1f',
        primary: {
          light: '#38bdf8',
          DEFAULT: '#0ea5e9',
          dark: '#0369a1',
        },
        danger: '#ef4444',
        warning: '#f59e0b',
        success: '#10b981',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      }
    },
  },
  plugins: [],
}
