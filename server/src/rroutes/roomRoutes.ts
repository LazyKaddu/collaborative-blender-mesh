// src/routes/roomRoutes.ts
import { Router, Request, Response } from 'express';
import { supabase } from '../config/supabase.js';
import { CacheService } from '../services/cacheService.js';

const router = Router();

// =========================================================================
// 1. ROUTE: ADAPTED CREATE ROOM
// =========================================================================
router.post('/create', async (req: Request, res: Response): Promise<any> => {
    try {
        const { filename, client_id } = req.body;

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
            timestamp: timestamp
        });

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
            timestamp: Number(activeRoom.timestamp)
        });

    } catch (error: any) {
        console.error('Metadata Fetch Failure:', error);
        return res.status(500).json({ error: error.message });
    }
});

// todo : complete the api route flush and then add the update room metadata route

// router.get('/flush/:roomId', async (req: Request, res: Response): Promise<any> => {
//     try {
//         const roomId = req.params.roomId as string;

//         const activeRoom = await CacheService.getRoomState(roomId);

//         if (!activeRoom) {
//             return res.status(404).json({ error: 'Session not found or has expired.' });
//         }

//         console.log(`👥 Metadata rehydrated for Room [${roomId}]`);



export default router;