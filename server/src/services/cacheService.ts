// src/services/cacheService.ts
import { redisClient } from '../config/redis.js';
import { MsgPackProtocol } from '../protocols/msgpack.js'

export class CacheService {
    private static ROOM_PREFIX = 'room:';

    static getOpKey(roomId: string) {
        return `room:${roomId}:operations`;
    }

    static async getRoomHistory(roomId: string, historyPointer: number): Promise<any> {
        const key = this.getOpKey(roomId);

        try {
            const raw = await redisClient.sendCommand(
                ['LRANGE', key, '0', '-1']
            ) as Buffer[] | string[];
            if (!raw || raw.length === 0) {
                return [];
            }

            const ops = raw.map(buf =>
                MsgPackProtocol.unpack(Buffer.isBuffer(buf) ? buf : Buffer.from(buf))
            );

            return ops.filter(op => op && op.seq >= historyPointer);

        } catch (error) {
            console.error(
                `❌ Failed to retrieve history for room [${roomId}]:`,
                error
            );
            throw error;
        }
    }

    static async setRoomHistory(roomId: string, operations: Buffer[]): Promise<void> {
        const key = this.getOpKey(roomId);

        await redisClient.del(key);

        if (!operations?.length) return;

        await redisClient.rPush(key, operations);
        await redisClient.expire(key, 86400);
    }

    static async appendOperation(roomId: string, packedData: Buffer): Promise<void> {
        const key = this.getOpKey(roomId);

        await redisClient.rPush(key, packedData);

        await redisClient.expire(key, 86400);
    }


    static async setRoomState(roomId: string, data: Record<string, any>): Promise<void> {
        const key = `${this.ROOM_PREFIX}${roomId}`;
        const fields: Record<string, string> = {};
        for (const [k, v] of Object.entries(data)) {
            fields[k] = typeof v === 'object' ? JSON.stringify(v) : String(v);
        }
        await redisClient.hSet(key, fields);
        await redisClient.expire(key, 86400); // 24 hours room TTL
    }

    static async getRoomState(roomId: string): Promise<Record<string, any> | null> {
        const key = `${this.ROOM_PREFIX}${roomId}`;
        const data = await redisClient.hGetAll(key);
        if (!data || Object.keys(data).length === 0) return null;

        const result: Record<string, any> = {};
        for (const [k, v] of Object.entries(data)) {
            try { result[k] = JSON.parse(v); } catch { result[k] = v; }
        }
        return result;
    }
}