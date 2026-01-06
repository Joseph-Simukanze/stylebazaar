/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',  // ← Enables dark mode toggle via .dark on <html>
  content: [
    "./templates/**/*.html",
    "./static/**/*.js",
    // Add any other folders with HTML/JS if needed
  ],
  theme: {
    extend: {
      colors: {
        primary: '#ec4899',
        'primary-hover': '#db2777',
      },
    },
  },
  plugins: [],
}
