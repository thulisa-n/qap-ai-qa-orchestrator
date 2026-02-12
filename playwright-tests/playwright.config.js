require('dotenv').config();
const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
  use: {
    baseURL: process.env.BASE_URL,
    trace: 'on-first-retry',
  },
});

