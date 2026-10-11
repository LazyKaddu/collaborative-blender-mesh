// src/routes/operationRoutes.ts
import { Router, Request, Response } from 'express';
import { redisClient } from '../config/redis.js';
import { OperationService } from '../services/operationService.js';
import { CacheService } from '../services/cacheService.js'

const router = Router();


const getOpKey = (roomId: string) => `room:${roomId}:operations`;

router.get('/history/:roomId/:historyPointer', async (
    req: Request,
    res: Response
): Promise<any> => {
    try {
        const roomId = req.params.roomId as string;

        const historyPointer = Number(req.params.historyPointer);

        const operations = await CacheService.getRoomHistory(roomId,historyPointer);

        const latestSeq = await OperationService.getLatestSequence(roomId);

        return res.status(200).json({
            operations,
            latest_seq: latestSeq
        });

    } catch (error: any) {
        console.error(
            '❌ Failed to fetch operation backlog:',
            error
        );

        return res.status(500).json({
            error: error.message
        });
    }
});

export default router;