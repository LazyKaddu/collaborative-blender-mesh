// src/gateway/socket.ts
import { Server as HttpServer } from 'http';
import { WebSocketServer, WebSocket } from 'ws';
import { CacheService } from '../services/cacheService.js';
import { MsgPackProtocol } from '../protocols/msgpack.js'; // 1. Import your new protocol wrapper
import {OperationService} from '../services/operationService.js'
import {RoomCleanupService} from '../services/roomCleanupService.js'

const roomCleanupTimers = new Map<
    string,
    NodeJS.Timeout
>();


function shouldPersist(packet: any): boolean {
    const persistentTypes = new Set([
        'COMMAND_EXECUTION',
        'STATE_RESYN',
        'BMESH_COMMIT_SYNC',
        'RENAME',
        'MATERIAL_CHANGE',
        'PARENT_CHANGE',
        'COLLECTION_CHANGE',
        'RELEASE_AND_SYNC'
    ]);

    return persistentTypes.has(packet.type);
}


interface CollabSocket extends WebSocket {
    roomId?: string;
    clientId?: string;
}

export function initWebSocketServer(server: HttpServer): void {
    const wss = new WebSocketServer({ noServer: true });

    server.on('upgrade', (request, socket, head) => {
        const url = new URL(request.url || '', `http://${request.headers.host}`);
        wss.handleUpgrade(request, socket, head, (ws) => {
            wss.emit('connection', ws, request);
        });
    });

    console.log('⚡ WebSocket Broker Gateway synchronized with Binary MessagePack Protocol.');

    wss.on('connection', (ws: CollabSocket) => {
        console.log('🔌 Blender binary channel established successfully.');
        ws.send(MsgPackProtocol.pack({
            type: "connectionStatus",
            status: "ready"
        }))
        console.log("send connection stats to client ")

        // 2. Change the incoming listener argument type to read raw data chunks
        ws.on('message', async (message: Buffer) => {
            try {
                // 3. Unpack the incoming MessagePack binary frame back into a JSON object
                const packet = MsgPackProtocol.unpack(message);
                console.log(packet)
                const { type, room_id, client_id } = packet;
                if (!ws.roomId && type !== 'join') {
                    console.warn(
                        'Client attempted to send packet before joining.'
                    );

                    ws.close(1008, 'Must join a room first');
                    return;
                }

                if (
                    ws.roomId &&
                    shouldPersist(packet)
                ) {
                    packet.seq =
                        await OperationService.getNextSequence(
                            ws.roomId
                        );

                    packet.timestamp = Date.now();

                    await OperationService.appendOperation(
                        ws.roomId,
                        packet
                    );
                }


                switch (type) {
                    case 'join': {
                        const activeRoom = await CacheService.getRoomState(room_id);
                        
                        const cleanupTimer = roomCleanupTimers.get(room_id);

                        if (cleanupTimer) {
                            clearTimeout(cleanupTimer);

                            roomCleanupTimers.delete(
                                room_id
                            );

                            console.log(`🟢 Cleanup cancelled for Room [${room_id}] because someone joined.`);
                        }
                        if (!activeRoom) {
                            // If an error happens, we still send a packed binary message back
                            ws.send(MsgPackProtocol.pack({ 
                                type: 'error', 
                                message: `Room [${room_id}] is missing or has expired.` 
                            }));
                            ws.close();
                            return;
                        }
                        const latestSeq =
                            await OperationService.getLatestSequence(
                                room_id
                            );

                        ws.roomId = room_id;
                        ws.clientId = client_id;

                        
                        ws.send(
                            MsgPackProtocol.pack({
                                type: 'join_accepted',
                                latest_seq: latestSeq,
                                download_url: activeRoom.download_url,
                                timestamp: Number(activeRoom.timestamp)
                            })
                        );

                        console.log(`📡 Linked Client [${client_id}] to Binary Active Space [${room_id}]`);
                        
                        broadcastToRoom(wss, room_id, client_id, {
                            type: 'peer_joined',
                            client_id
                        });
                        break;
                    }

                    default: {
                        if (ws.roomId && ws.clientId) {
                            if (shouldPersist(packet)) {
                                broadcastToRoom(
                                    wss,
                                    ws.roomId,
                                    ws.clientId,
                                    packet
                                );
                            } else {
                                broadcastToRoomRaw(
                                    wss,
                                    ws.roomId,
                                    ws.clientId,
                                    message
                                );
                            }
                        }
                    }
                }

            } catch (err) {
                console.error('❌ Failed to process binary packet payload:', err);
            }
        });

        ws.on('close', () => {
            if (ws.roomId && ws.clientId) {
                console.log(`🔌 Client [${ws.clientId}] exited connection from Room [${ws.roomId}]`);
                
                broadcastToRoom(wss, ws.roomId, ws.clientId, {
                    type: 'peer_left',
                    client_id: ws.clientId
                });

                checkRoomVacancy(wss, ws.roomId);
            }
        });
    });
}

/**
 * Standard Broadcaster: Packs an object to binary before broadcasting
 */
function broadcastToRoom(wss: WebSocketServer, roomId: string, senderClientId: string, payload: object): void {
    const binaryPayload = MsgPackProtocol.pack(payload); // Compress object to binary

    wss.clients.forEach((client: CollabSocket) => {
        if (client.readyState === WebSocket.OPEN && client.roomId === roomId && client.clientId !== senderClientId) {
            client.send(binaryPayload);
        }
    });
}

/**
 * High-Frequency Broadcaster Optimization: Pipes an already packed buffer directly 
 * to save server CPU cycles.
 */
function broadcastToRoomRaw(wss: WebSocketServer, roomId: string, senderClientId: string, rawBuffer: Buffer): void {
    wss.clients.forEach((client: CollabSocket) => {
        if (client.readyState === WebSocket.OPEN && client.roomId === roomId && client.clientId !== senderClientId) {
            client.send(rawBuffer); // Stream raw binary array straight through
        }
    });
}

function checkRoomVacancy(wss: WebSocketServer, roomId: string): void {
    let occupants = 0;
    wss.clients.forEach((client: CollabSocket) => {
        if (client.roomId === roomId && client.readyState === WebSocket.OPEN) occupants++;
    });
    if (occupants === 0) {
        console.log(`🥀 All clients have disconnected from Room [${roomId}]. Redis cache will auto-expire.`);
        if (!roomCleanupTimers.has(roomId)) {
            const timer = setTimeout(async () => {
                await RoomCleanupService.cleanupRoom(
                    roomId
                );

                roomCleanupTimers.delete(
                    roomId
                );
            }, 5 * 60 * 1000);

            roomCleanupTimers.set(
                roomId,
                timer
            );
}
    }
}