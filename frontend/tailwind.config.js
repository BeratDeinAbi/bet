/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: '#0f0f0f',
          low: '#131313',
          mid: '#1a1a1a',
          high: '#222222',
          border: '#2a2a2a',
        },
        accent: {
          green: '#8eff71',
          blue: '#60a5fa',
          amber: '#fbbf24',
          red: '#f87171',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['Manrope', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
