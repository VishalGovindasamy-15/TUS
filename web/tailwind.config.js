/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: { 50: '#eef6ff', 600: '#1d4ed8', 700: '#1e40af' },
      },
    },
  },
  plugins: [],
};
