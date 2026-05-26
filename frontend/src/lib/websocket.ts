/**
 * WebSocket client for real-time backtest streaming.
 */

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

export type WsMessage =
  | { type: "progress"; message: string }
  | { type: "result"; data: Record<string, unknown> }
  | { type: "error"; message: string };

export function createBacktestWs(
  params: Record<string, unknown>,
  callbacks: {
    onProgress?: (msg: string) => void;
    onResult?: (data: Record<string, unknown>) => void;
    onError?: (msg: string) => void;
    onClose?: () => void;
  }
): WebSocket {
  const ws = new WebSocket(`${WS_BASE}/ws/backtest`);

  ws.onopen = () => {
    ws.send(JSON.stringify(params));
  };

  ws.onmessage = (event) => {
    try {
      const msg: WsMessage = JSON.parse(event.data);
      switch (msg.type) {
        case "progress":
          callbacks.onProgress?.(msg.message);
          break;
        case "result":
          callbacks.onResult?.(msg.data);
          break;
        case "error":
          callbacks.onError?.(msg.message);
          break;
      }
    } catch {
      callbacks.onError?.("Failed to parse server message");
    }
  };

  ws.onerror = () => callbacks.onError?.("WebSocket connection error");
  ws.onclose = () => callbacks.onClose?.();

  return ws;
}
