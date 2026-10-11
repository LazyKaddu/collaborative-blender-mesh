// src/services/operationService.ts
import { redisClient } from '../config/redis.js';

export class OperationService {

    static getSeqKey(roomId: string) {
        return `room:${roomId}:seq`;
    }

    static async getNextSequence(
        roomId: string
    ): Promise<number> {
        const seq = await redisClient.incr(
            this.getSeqKey(roomId)
        );

        await redisClient.expire(
            this.getSeqKey(roomId),
            86400
        );

        return seq;
    }
    static async getLatestSequence(roomId: string) {
        const seq = await redisClient.get(
            `room:${roomId}:seq`
        );

        return Number(seq ?? 0);
    }
}

