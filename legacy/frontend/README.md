# Frontend Overview

React/Vite dashboard for Market Sentiment Intelligence.

## Pages
- Dashboard
- Sentiment Analyzer
- Predictions
- Backtest
- Trade Log

## Data Layer
- `src/services/apiClient.js` handles all backend calls.
- `src/hooks/usePollingQuery.js` provides shared polling behavior and hidden-tab pause.

## Run
- `npm install`
- `npm run dev`
