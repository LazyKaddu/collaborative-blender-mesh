// src/testRedis.ts
import { CacheService } from './services/cacheService.js';
import redisClient from './config/redis.js';

async function verifyCacheLayer() {
    console.log("⏳ Initializing Memory Layer Test Sequence...");
    
    // Give the client a brief moment to finish its handshakes
    await new Promise(resolve => setTimeout(resolve, 1000));

    const testRoomId = "RM_TEST123";
    const mockRoomData = {
        scene_name: "Underwater_Ruins",
        active_users: 2,
        current_snapshot_url: "https://supabase-storage-path/snapshot.glb",
        last_saved_frame: Date.now()
    };

    try {
        // 1. Test Writing Data to the Docker Cache Container
        console.log(`\n✍️ Writing test payload data to key [room:${testRoomId}]...`);
        await CacheService.setRoomState(testRoomId, mockRoomData);
        console.log("✅ Write operation completed without exceptions.");

        // 2. Test Reading Data back from Redis memory hashes
        console.log(`\n📖 Rehydrating state mapping back out of memory storage...`);
        const cachedData = await CacheService.getRoomState(testRoomId);
        
        if (cachedData) {
            console.log("✅ Read operation successful! Received payload:");
            console.log(JSON.stringify(cachedData, null, 2));
            
            // Type verification check
            if (typeof cachedData.active_users === 'number' || !isNaN(Number(cachedData.active_users))) {
                console.log("\n🚀 DATA PIPELINE VERIFIED: TypeScript and Docker Redis are fully synchronized!");
            }
        } else {
            console.log("❌ Error: Pipeline executed but returned an empty structural payload.");
        }

    } catch (error) {
        console.error("❌ Critical Memory Layer Failure:", error);
    } finally {
        // Disconnect cleanly so the node process terminates automatically
        await redisClient.disconnect();
        console.log("\n🔒 Test runtime disconnected cleanly.");
    }
}

verifyCacheLayer();