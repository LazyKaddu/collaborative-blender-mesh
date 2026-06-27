// src/services/operationService.ts
import redisClient from '../config/redis.js';

export class OperationService {
    static getOpKey(roomId: string) {
        return `room:${roomId}:operations`;
    }

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
            7200
        );

        return seq;
    }
    static async getLatestSequence(roomId: string) {
        const seq = await redisClient.get(
            `room:${roomId}:seq`
        );

        return Number(seq ?? 0);
    }

    static async appendOperation(
        roomId: string,
        operation: any
    ): Promise<void> {
        await redisClient.rPush(
            this.getOpKey(roomId),
            JSON.stringify(operation)
        );

        await redisClient.expire(
            this.getOpKey(roomId),
            7200
        );
    }
}

