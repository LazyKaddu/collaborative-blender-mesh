import { createClient } from 'redis';
import dotenv from 'dotenv';

dotenv.config();

// Initialize the Redis client instance mapping
export const redisClient = createClient({
    url: process.env.REDIS_URL || 'redis://127.0.0.1:6379'
});

redisClient.on('error', (err) => {
    console.error('❌ Redis Engine Connection Error:', err);
});

redisClient.on('connect', () => {
    console.log('📦 Redis Cache Engine connected successfully.');
});

export const pubClient = redisClient.duplicate();
export const subClient = redisClient.duplicate();

// Immediately Invoked Execution function to connect to the memory grid automatically
export async function connectRedis() {
    if (!redisClient.isOpen) {
        await redisClient.connect();
    }

    if (!pubClient.isOpen) {
        await pubClient.connect();
    }

    if (!subClient.isOpen) {
        await subClient.connect();
    }

    console.log("🚀 Redis (main + pub + sub) fully connected");
}

