/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Helle Basis: leicht kühler Off-White-Ton mit Grün-Undertone.
        // Kein reines Weiß — das ermüdet die Augen bei langen Sessions.
        canvas: {
          DEFAULT: '#f5f7f4',  // Page-Background
          1: '#ffffff',         // Card-Surface (volle Helligkeit)
          2: '#eef1ec',         // gehobene Surface
          3: '#e3e7e0',         // sekundäre Surface
          line: '#e1e5dd',      // sehr feine Trennlinie
          border: '#cdd3c8',    // sichtbare Borders
        },
        // Text-Hierarchie
        text: {
          DEFAULT: '#1a1f1a',  // Primary (fast schwarz)
          dim: '#3d4540',      // Sekundärer Body-Text
          mute: '#6b7280',     // Labels / Subtitles
          quiet: '#9ca3af',    // Meta / Disabled
        },
        // Grüner Akzent — gedeckt, nicht neon-grün
        accent: {
          DEFAULT: '#2d7a3e',
          bright: '#3fa356',
          soft: '#dcebe0',     // Heller Tint für Backgrounds
          dim: '#1f5c2d',
          // Backwards-compat-Aliase für alte Komponenten
          green: '#2d7a3e',
          blue: '#0369a1',
          amber: '#b45309',
          red: '#c2410c',
        },
        // Status-Farben — alle für hellen Hintergrund optimiert
        pos: '#2d7a3e',
        neg: '#c2410c',
        warn: '#b45309',
        live: '#dc2626',

        // Kompatibilitäts-Aliasse, damit ältere Komponenten weiter rendern.
        // (Werden über die Zeit weggeräumt.)
        ink: {
          DEFAULT: '#f5f7f4',
          1: '#ffffff',
          2: '#eef1ec',
          3: '#e3e7e0',
          line: '#e1e5dd',
          border: '#cdd3c8',
        },
        paper: {
          DEFAULT: '#1a1f1a',
          dim: '#3d4540',
          mute: '#6b7280',
          quiet: '#9ca3af',
        },
        signal: {
          DEFAULT: '#2d7a3e',
          high: '#3fa356',
          dim: '#1f5c2d',
        },
        surface: {
          DEFAULT: '#f5f7f4',
          low: '#ffffff',
          mid: '#ffffff',
          high: '#eef1ec',
          border: '#e1e5dd',
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
