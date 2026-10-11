// src/routes/roomRoutes.ts
import { Router, Request, Response } from 'express';
import { supabase } from '../config/supabase.js';
import { CacheService } from '../services/cacheService.js';
import { OperationService } from '../services/operationService.js'

const router = Router();

// =========================================================================
// 1. ROUTE: ADAPTED CREATE ROOM
// =========================================================================
router.post('/create', async (req: Request, res: Response): Promise<any> => {
    try {
        const { filename, client_id, mesh_data } = req.body;

        if (!filename || !client_id) {
            return res.status(400).json({ error: 'Missing filename or client_id in payload.' });
        }

        // Generate a clean 6-character room code (e.g., 'RM-A3F2')
        const roomId = `RM-${Math.random().toString(36).substring(2, 8).toUpperCase()}`;
        
        // Isolate file extension to append to our clean unique cloud path
        const fileExtension = filename.split('.').pop() || 'glb';
        const cloudFilename = `${roomId}_${Date.now()}.${fileExtension}`;

        // Request a single-use upload link from Supabase Storage
        const { data, error: storageError } = await supabase.storage
            .from('blender-scenes')
            .createSignedUploadUrl(cloudFilename);

        if (storageError || !data) {
            throw new Error(`Cloud token extraction failed: ${storageError?.message}`);
        }

        // Get the public path where other peers can download it
        const { data: publicUrlData } = supabase.storage
            .from('blender-scenes')
            .getPublicUrl(cloudFilename);

        const downloadUrl = publicUrlData.publicUrl;
        const timestamp = Date.now();

        // Push data layout frame to Redis match structure
        await CacheService.setRoomState(roomId, {
            room_id: roomId,
            download_url: downloadUrl,
            storage_filename: cloudFilename,
            creator_client_id: client_id,
            timestamp: timestamp,
            mesh_data: mesh_data,
            history_pointer: 0,
        });

        await CacheService.setRoomHistory(roomId,[]);

        console.log(`Room [${roomId}] pre-signed out to Client [${client_id}]`);
        console.log(`pre-signed url - ${downloadUrl}`)

        // Return EXACT signature your Python script expects: { room_id, upload_url, download_url }
        return res.status(201).json({
            room_id: roomId,
            upload_url: data.signedUrl,
            download_url: downloadUrl
        });

    } catch (error: any) {
        console.error('❌ Room Adapt Create Failure:', error);
        return res.status(500).json({ error: error.message });
    }
});

// =========================================================================
// 2. ROUTE: ADAPTED JOIN / FETCH METADATA
// =========================================================================
router.get('/join/:roomId', async (req: Request, res: Response): Promise<any> => {
    try {
        const roomId = req.params.roomId as string;

        const activeRoom = await CacheService.getRoomState(roomId);

        if (!activeRoom) {
            return res.status(404).json({ error: 'Session not found or has expired.' });
        }

        console.log(`👥 Metadata rehydrated for Room [${roomId}]`);

        // Return EXACT signature your python script expects: { download_url, timestamp }
        return res.status(200).json({
            download_url: activeRoom.download_url,
            timestamp: Number(activeRoom.timestamp),
            mesh_data: activeRoom.mesh_data,
            history_pointer: activeRoom.history_pointer,
        });

    } catch (error: any) {
        console.error('Metadata Fetch Failure:', error);
        return res.status(500).json({ error: error.message });
    }
});




router.post('/flush/:roomId', async (req: Request, res: Response): Promise<any> => {
    try {
        const roomId = req.params.roomId as string;
        const { filename } = req.body;

        const latestSeq = await OperationService.getLatestSequence(roomId);

        if (!filename) {
            return res.status(400).json({ error: 'Missing filename in payload.' });
        }

        // Verify room state layer exists before granting tokens
        const activeRoom = await CacheService.getRoomState(roomId);
        if (!activeRoom) {
            return res.status(404).json({ error: 'Session not found or has expired.' });
        }


        // Generate an isolated, unique future cloud filename
        const fileExtension = filename.split('.').pop() || 'glb';
        const nextCloudFilename = `${roomId}_${Date.now()}.${fileExtension}`;

        // Request single-use write token permission from Supabase Storage
        const { data, error: storageError } = await supabase.storage
            .from('blender-scenes')
            .createSignedUploadUrl(nextCloudFilename);

        if (storageError || !data) {
            throw new Error(`Failed to generate signed upload URL: ${storageError?.message}`);
        }

        console.log(`📡 Issued background upload token for Room [${roomId}] -> File: ${nextCloudFilename}`);

        // Return ONLY the critical ticket parameters back to the client
        return res.status(200).json({
            room_id: roomId,
            upload_url: data.signedUrl,
            future_filename: nextCloudFilename, // Passing this back so client can send it back to step 2
            latest_seq: latestSeq,
        });

    } catch (error: any) {
        console.error('❌ Flush Token Generation Failure:', error);
        return res.status(500).json({ error: error.message });
    }
});

// =========================================================================
// STEP 2: UPDATE METADATA (Deletes Old Asset & Rehydrates Redis State)
// =========================================================================
router.put('/update-metadata/:roomId', async (req: Request, res: Response): Promise<any> => {
    try {
        const roomId = req.params.roomId as string;
        const { future_filename, mesh_data, historyPointer } = req.body; // Received back from the client post-upload success

        if (!future_filename) {
            return res.status(400).json({ error: 'Missing future_filename in payload metadata update.' });
        }

        // Fetch current snapshot before committing state changes
        const activeRoom = await CacheService.getRoomState(roomId);
        if (!activeRoom) {
            return res.status(404).json({ error: 'Active workspace cluster state not found.' });
        }

        const oldStorageFilename = activeRoom.storage_filename;

        // Extract the fresh absolute public URL for the newly uploaded file
        const { data: publicUrlData } = supabase.storage
            .from('blender-scenes')
            .getPublicUrl(future_filename);

        const newDownloadUrl = publicUrlData.publicUrl;
        const currentTimestamp = Date.now();

        // 1. Commit and flash the clean new metadata array to Redis
        await CacheService.setRoomState(roomId, {
            ...activeRoom,
            download_url: newDownloadUrl,
            storage_filename: future_filename,
            timestamp: currentTimestamp,
            mesh_data: mesh_data,
            history_pointer: historyPointer,
        });

        // 2. Perform the destructive extraction delete on the old asset file
        if (oldStorageFilename && oldStorageFilename !== future_filename) {
            const { error: deleteError } = await supabase.storage
                .from('blender-scenes')
                .remove([oldStorageFilename]);

            if (deleteError) {
                console.error(`⚠️ Garbage collection warning: Failed to purge ${oldStorageFilename}:`, deleteError.message);
            } else {
                console.log(`🗑️ Cleaned up leaked previous storage asset: ${oldStorageFilename}`);
            }
        }

        console.log(`🔥 Metadata state fully synchronized and old assets flushed for Room [${roomId}]`);
        
        return res.status(200).json({
            status: "success",
            download_url: newDownloadUrl,
            timestamp: currentTimestamp
        });

    } catch (error: any) {
        console.error('❌ Post-Upload Metadata Sync Failure:', error);
        return res.status(500).json({ error: error.message });
    }
});

export default router;