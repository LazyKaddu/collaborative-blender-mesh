// src/server.ts
import express from 'express';
import cors from 'cors';
import http from 'http';
import apiRouter from './rroutes/routes.js'; // Single import for all routes 🚀
import { initSocketIOServer } from './gateway/socket.js';
import { connectRedis } from './config/redis.js'
import rateLimit from "express-rate-limit";


// rate limitter 
const apiLimiter = rateLimit({
    windowMs: 60 * 1000,
    max: 100,
    message: {
        error: "Too many requests"
    },
    standardHeaders: true,
    legacyHeaders: false
});


const app = express();
const port = process.env.PORT || 8080;

await connectRedis();

app.use(cors());
app.use(express.json());

app.use("/api", apiLimiter);

// Bind your central router hub to the /api base path
app.use('/api', apiRouter);

app.get("/", (req, res) => {
    res.send("OK");
});

const server = http.createServer(app);

// Attach your real-time WebSocket Gateway
initSocketIOServer(server);

server.listen(Number(port), "0.0.0.0", () => {
    console.log(`🚀 Unified API and Gateway active on http://localhost:${port}`);
    console.log(`📁 Central Router loaded. Core paths mapped:`);
    console.log(`   ➔ HTTP  - http://localhost:${port}/api/room/*`);
    console.log(`   ➔ HTTP  - http://localhost:${port}/api/operation/*`);
    console.log(`   ➔ WS    - ws://localhost:${port}/`);
});