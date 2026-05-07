/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Warme, papier-artige Off-Schwarz-Palette.  Nicht das übliche
        // #0d0d0d-Tech-Grau, sondern leicht warm, damit Serif-Typo
        // weniger steril wirkt.
        ink: {
          DEFAULT: '#0e0d0a',
          1: '#15140f',
          2: '#1c1a14',
          3: '#26231c',
          line: '#2d2a23',
          border: '#3a362d',
        },
        paper: {
          DEFAULT: '#f3ede0',
          dim: '#cfc7b6',
          mute: '#8a8478',
          quiet: '#5b574e',
        },
        // Ein einziger, gesetzter Akzent — Terracotta.  Liest sich
        // nach „menschlich" statt nach „Tailwind blue".
        signal: {
          DEFAULT: '#d97757',
          high: '#e89674',
          dim: '#a85a3f',
        },
        live: '#dd4444',
        pos: '#7a9e6e',
        neg: '#c75a5a',

        // Backwards-compat aliases — werden in alten Komponenten noch
        // referenziert.  Mappen auf die neuen Tokens.
        surface: {
          DEFAULT: '#0e0d0a',
          low: '#15140f',
          mid: '#1c1a14',
          high: '#26231c',
          border: '#2d2a23',
        },
        accent: {
          green: '#7a9e6e',
          blue: '#9bb7d4',
          amber: '#d9a25a',
          red: '#c75a5a',
        },
      },
      fontFamily: {
        // Fraunces: kontrastreicher Modern-Serif mit Persönlichkeit
        //   → Headlines, Liga-Tag, Zahlen-Typografie.
        // IBM Plex Sans: ruhiger Body-Sans, weniger generisch als Inter.
        // IBM Plex Mono: für Stats und tabellarische Zahlen.
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
