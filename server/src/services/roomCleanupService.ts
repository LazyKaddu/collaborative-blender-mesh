// src/services/roomCleanupService.ts

import redisClient from '../config/redis.js';
import { supabase } from '../config/supabase.js';
import { CacheService } from './cacheService.js';

export class RoomCleanupService {
    static async cleanupRoom(
        roomId: string
    ): Promise<void> {
        const room =
            await CacheService.getRoomState(roomId);

        if (!room) {
            return;
        }

        try {
            // Delete snapshot from Supabase
            if (room.storage_filename) {
                await supabase.storage
                    .from('blender-scenes')
                    .remove([
                        room.storage_filename
                    ]);
            }

            // Delete all Redis keys
            await redisClient.del([
                `room:${roomId}`,
                `room:${roomId}:operations`,
                `room:${roomId}:seq`,
                `room:${roomId}:baseline_seq`
            ]);

            console.log(
                `🗑️ Room [${roomId}] fully cleaned up.`
            );
        }
        catch (err) {
            console.error(
                `❌ Failed to clean room [${roomId}]`,
                err
            );
        }
    }
}