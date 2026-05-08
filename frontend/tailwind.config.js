/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        canvas: {
          DEFAULT: 'rgb(var(--canvas) / <alpha-value>)',
          1: 'rgb(var(--canvas-1) / <alpha-value>)',
          2: 'rgb(var(--canvas-2) / <alpha-value>)',
          3: 'rgb(var(--canvas-3) / <alpha-value>)',
          line: 'rgb(var(--canvas-line) / <alpha-value>)',
          border: 'rgb(var(--canvas-border) / <alpha-value>)',
        },
        text: {
          DEFAULT: 'rgb(var(--text) / <alpha-value>)',
          dim: 'rgb(var(--text-dim) / <alpha-value>)',
          mute: 'rgb(var(--text-mute) / <alpha-value>)',
          quiet: 'rgb(var(--text-quiet) / <alpha-value>)',
        },
        accent: {
          DEFAULT: 'rgb(var(--accent) / <alpha-value>)',
          bright: 'rgb(var(--accent-bright) / <alpha-value>)',
          soft: 'rgb(var(--accent-soft) / <alpha-value>)',
          dim: 'rgb(var(--accent-dim) / <alpha-value>)',
          // Backwards-compat aliasse
          green: 'rgb(var(--accent) / <alpha-value>)',
          blue: 'rgb(var(--info) / <alpha-value>)',
          amber: 'rgb(var(--warn) / <alpha-value>)',
          red: 'rgb(var(--neg) / <alpha-value>)',
        },
        pos: 'rgb(var(--pos) / <alpha-value>)',
        neg: 'rgb(var(--neg) / <alpha-value>)',
        warn: 'rgb(var(--warn) / <alpha-value>)',
        live: 'rgb(var(--live) / <alpha-value>)',
        info: 'rgb(var(--info) / <alpha-value>)',

        // Compat-Aliasse für alte Komponenten (nutzen die gleichen Tokens)
        ink: {
          DEFAULT: 'rgb(var(--canvas) / <alpha-value>)',
          1: 'rgb(var(--canvas-1) / <alpha-value>)',
          2: 'rgb(var(--canvas-2) / <alpha-value>)',
          3: 'rgb(var(--canvas-3) / <alpha-value>)',
          line: 'rgb(var(--canvas-line) / <alpha-value>)',
          border: 'rgb(var(--canvas-border) / <alpha-value>)',
        },
        paper: {
          DEFAULT: 'rgb(var(--text) / <alpha-value>)',
          dim: 'rgb(var(--text-dim) / <alpha-value>)',
          mute: 'rgb(var(--text-mute) / <alpha-value>)',
          quiet: 'rgb(var(--text-quiet) / <alpha-value>)',
        },
        signal: {
          DEFAULT: 'rgb(var(--accent) / <alpha-value>)',
          high: 'rgb(var(--accent-bright) / <alpha-value>)',
          dim: 'rgb(var(--accent-dim) / <alpha-value>)',
        },
        surface: {
          DEFAULT: 'rgb(var(--canvas) / <alpha-value>)',
          low: 'rgb(var(--canvas-1) / <alpha-value>)',
          mid: 'rgb(var(--canvas-1) / <alpha-value>)',
          high: 'rgb(var(--canvas-2) / <alpha-value>)',
          border: 'rgb(var(--canvas-line) / <alpha-value>)',
        },
      },
      fontFamily: {
        display: ['"Fraunces"', 'Georgia', 'serif'],
        sans: ['"IBM Plex Sans"', 'system-ui', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
      },
      letterSpacing: {
        tightish: '-0.012em',
        tighter2: '-0.025em',
      },
    },
  },
  plugins: [],
}
