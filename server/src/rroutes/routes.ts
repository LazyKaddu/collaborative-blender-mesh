// src/routes/routes.ts
import { Router } from 'express';
import roomRoutes from './roomRoutes.js';
import operationRoutes from './operationRoutes.js';

const apiRouter = Router();

// Map your sub-routers to their respective domain paths
apiRouter.use('/room', roomRoutes);           // Maps all routes to /api/room/*
apiRouter.use('/operation', operationRoutes);   // Maps all routes to /api/operation/*

export default apiRouter;