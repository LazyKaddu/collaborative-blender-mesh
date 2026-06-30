// src/routes/routes.ts
import { Router, Request, Response } from 'express';
import roomRoutes from './roomRoutes.js';
import operationRoutes from './operationRoutes.js';

const apiRouter = Router();

// Map your sub-routers to their respective domain paths
apiRouter.use('/room', roomRoutes);           // Maps all routes to /api/room/*
apiRouter.use('/operation', operationRoutes);   // Maps all routes to /api/operation/*

apiRouter.get('/health', (req: Request, res: Response)=> {
    try {
        res.status(200).json({
            status: "healthy",
            timestamp: new Date().toISOString(),
            uptime: process.uptime()
        });
    } catch (error) {
        res.status(500).json({ status: "unhealthy", error: String(error) });
    }
});

export default apiRouter;