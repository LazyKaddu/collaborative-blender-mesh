// src/protocols/msgpack.ts
import { encode, decode } from '@msgpack/msgpack';

export class MsgPackProtocol {
    /**
     * Serializes a JavaScript Object/Array into a compact binary Buffer
     * ready to be sent over a raw WebSocket channel.
     */
    static pack(payload: Record<string, any> | any[]): Buffer {
        const serializedUint8 = encode(payload);
        // Wrap it in a Node.js Buffer for clean compatibility with the 'ws' package
        return Buffer.from(serializedUint8.buffer, serializedUint8.byteOffset, serializedUint8.byteLength);
    }

    /**
     * Deserializes an incoming binary Buffer back into a native structured 
     * JavaScript object.
     */
    static unpack(buffer: Buffer | ArrayBuffer): any {
        // Convert Node Buffer safely back into a Uint8Array for decoding
        const uint8Array = buffer instanceof Buffer 
            ? new Uint8Array(buffer.buffer, buffer.byteOffset, buffer.byteLength)
            : new Uint8Array(buffer);
            
        return decode(uint8Array);
    }
}