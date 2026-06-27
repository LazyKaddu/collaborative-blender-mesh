import { createClient } from 'redis';
import dotenv from 'dotenv';

dotenv.config();

// Initialize the Redis client instance mapping
const redisClient = createClient({
    url: process.env.REDIS_URL || 'redis://127.0.0.1:6379'
});

redisClient.on('error', (err) => {
    console.error('❌ Redis Engine Connection Error:', err);
});

redisClient.on('connect', () => {
    console.log('📦 Redis Cache Engine connected successfully.');
});

// Immediately Invoked Execution function to connect to the memory grid automatically
(async () => {
    if (!redisClient.isOpen) {
        await redisClient.connect();
    }
})();

export default redisClient;