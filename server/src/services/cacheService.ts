// src/services/cacheService.ts
import redisClient from '../config/redis.js';

export class CacheService {
    private static ROOM_PREFIX = 'room:';

    static async setRoomState(roomId: string, data: Record<string, any>): Promise<void> {
        const key = `${this.ROOM_PREFIX}${roomId}`;
        const fields: Record<string, string> = {};
        for (const [k, v] of Object.entries(data)) {
            fields[k] = typeof v === 'object' ? JSON.stringify(v) : String(v);
        }
        await redisClient.hSet(key, fields);
        await redisClient.expire(key, 7200); // 2 hours room TTL
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