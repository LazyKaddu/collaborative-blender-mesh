// src/server.ts
import express from 'express';
import cors from 'cors';
import http from 'http';
import apiRouter from './rroutes/routes.js'; // Single import for all routes 🚀
import { initWebSocketServer } from './gateway/socket.js';

const app = express();
const port = process.env.PORT || 8080;

app.use(cors());
app.use(express.json());

// Bind your central router hub to the /api base path
app.use('/api', apiRouter);

const server = http.createServer(app);

// Attach your real-time WebSocket Gateway
initWebSocketServer(server);

server.listen(port, () => {
    console.log(`🚀 Unified API and Gateway active on http://localhost:${port}`);
    console.log(`📁 Central Router loaded. Core paths mapped:`);
    console.log(`   ➔ HTTP  - http://localhost:${port}/api/room/*`);
    console.log(`   ➔ HTTP  - http://localhost:${port}/api/operation/*`);
    console.log(`   ➔ WS    - ws://localhost:${port}/`);
});