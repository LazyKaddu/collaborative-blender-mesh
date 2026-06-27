// src/routes/operationRoutes.ts
import { Router, Request, Response } from 'express';
import redisClient from '../config/redis.js';
import { OperationService } from '../services/operationService.js';


const router = Router();


const getOpKey = (roomId: string) => `room:${roomId}:operations`;

router.get('/history/:roomId', async (
    req: Request,
    res: Response
): Promise<any> => {
    try {
        const roomId = req.params.roomId as string;

        const rawOps = await redisClient.lRange(
            getOpKey(roomId),
            0,
            -1
        );

        const operations = rawOps.map(op => JSON.parse(op));

        const latestSeq =
            await OperationService.getLatestSequence(
                roomId
            );

        console.log(
            `📜 Served ${operations.length} operations for Room [${roomId}]`
        );

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