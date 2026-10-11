import { Server as HttpServer } from "http";
import { Server, Socket } from "socket.io";
import { CacheService } from "../services/cacheService.js";
import { OperationService } from "../services/operationService.js";
import { RoomCleanupService } from "../services/roomCleanupService.js";
import { redisClient, pubClient, subClient } from "../config/redis.js";
import { MsgPackProtocol } from '../protocols/msgpack.js'
import { RateLimiterRedis } from "rate-limiter-flexible";
import { createAdapter } from "@socket.io/redis-adapter";


const roomCleanupTimers = new Map<string, NodeJS.Timeout>();

// pub-sub redis instance for io cluster

const connectionLimiter = new RateLimiterRedis({
    storeClient: redisClient,
    keyPrefix: "socket_connect",
    points: 20,
    duration: 60,
});

function shouldPersist(packet: any): boolean {
    const persistentTypes = new Set([
        "COMMAND_EXECUTION",
        "STATE_RESYN",
        "BMESH_COMMIT_SYNC",
        "RENAME",
        "MATERIAL_CHANGE",
        "PARENT_CHANGE",
        "COLLECTION_CHANGE",
        "RELEASE_AND_SYNC"
    ]);

    return persistentTypes.has(packet.type);
}

export function initSocketIOServer(server: HttpServer): void {
    const io = new Server(server, {
        cors: { origin: "*" }
    });

    console.log("⚡ Socket.IO Gateway initialized with MessagePack pipeline");

    io.adapter(createAdapter(pubClient, subClient));
    console.log("pub/sub for socket created ")



    // io.use(async (socket, next) => {

    //     try {

    //         await connectionLimiter.consume(
    //             socket.handshake.address!
    //         );

    //         next();

    //     } catch (err) {

    //         console.log(
    //             `❌ Rate limit exceeded for ${socket.handshake.address}`
    //         );

    //         next(new Error("Too many connection attempts"));

    //     }

    // });


    io.on("connection", (socket: Socket) => {
    console.log("🔌 Client connected:", socket.id);

    socket.emit("connectionStatus", {
        type: "connectionStatus",
        status: "ready"
    });

        socket.on("join", async ({ room_id, client_id }) => {
            const activeRoom = await CacheService.getRoomState(room_id);

            const cleanupTimer = roomCleanupTimers.get(room_id);

            if (cleanupTimer) {
                clearTimeout(cleanupTimer);
                roomCleanupTimers.delete(room_id);
            }

            if (!activeRoom) {
                socket.emit("error", {
                    type: "error",
                    message: `Room [${room_id}] is missing or expired.`
                });

                socket.disconnect();
                return;
        }

        const latestSeq =
            await OperationService.getLatestSequence(room_id);

        socket.join(room_id);

        // attach metadata (Socket.IO equivalent of ws.roomId/clientId)
        socket.data.roomId = room_id;
        socket.data.clientId = client_id;

        socket.emit("join_accepted", {
            latest_seq: latestSeq,
            download_url: activeRoom.download_url,
            timestamp: Number(activeRoom.timestamp)
        });

        console.log(`📡 Client ${client_id} joined room ${room_id}`);

        socket.to(room_id).emit("peer_joined", {
            client_id
        });
    });

    socket.on("message", async (incoming_packet: any) => {
    try {
        packet = MsgPackProtocol.unpack(incoming_packet);
        
        const { type, room_id, client_id } = packet
        console.log(`packet arrived with roomId ${room_id} and clientId ${client_id}`)
        const roomId = socket.data.roomId;

        if (!roomId && type !== "join") {
            socket.disconnect();
            return;
        }

        // sequence + timestamp injection (same as your logic)
        if (roomId && shouldPersist(packet)) {
            packet.seq = await OperationService.getNextSequence(roomId);
            packet.timestamp = Date.now();
        }

        switch (type) {
            default: {
                const packed =
                    MsgPackProtocol.pack(packet);

                await CacheService.appendOperation(roomId, packed);

                // broadcast logic
                if (shouldPersist(packet)) {
                    io.to(roomId).emit("message", packet);
                } else {
                    socket.to(roomId).emit("message_raw", packet);
                }

                break;
             }
        }
    } catch (err) {
        console.error("❌ Failed to process packet:", err);
    }
    });

    socket.on("disconnect", () => {
    const roomId = socket.data.roomId;
    const clientId = socket.data.clientId;

    if (!roomId || !clientId) return;

    console.log(`🔌 Client ${clientId} disconnected from ${roomId}`);

    socket.to(roomId).emit("peer_left", {
        client_id: clientId
    });

    checkRoomVacancy(io, roomId);
        });
    });
}


function checkRoomVacancy(io: Server, roomId: string): void {
    const room = io.sockets.adapter.rooms.get(roomId);

    const occupants = room ? room.size : 0;

    if (occupants === 0) {
        console.log(`🥀 Room ${roomId} is empty`);

        if (!roomCleanupTimers.has(roomId)) {
            const timer = setTimeout(async () => {
                await RoomCleanupService.cleanupRoom(roomId);
                roomCleanupTimers.delete(roomId);
            }, 5 * 60 * 1000);

            roomCleanupTimers.set(roomId, timer);
        }
    }
}



