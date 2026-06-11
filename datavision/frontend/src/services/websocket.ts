/**
 * WebSocket 服务 - 看板实时数据推送
 */

type MessageHandler = (data: unknown) => void;

class WSManager {
  private ws: WebSocket | null = null;
  private handlers: Map<string, Set<MessageHandler>> = new Map();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private url: string = '';
  private shouldReconnect: boolean = true;

  /**
   * 连接到看板 WebSocket
   */
  connect(dashboardId: string) {
    const token = localStorage.getItem('access_token');
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;

    this.url = `${protocol}//${host}/api/v1/ws/dashboard/${dashboardId}?token=${token}`;
    this.shouldReconnect = true;
    this._createConnection();
  }

  /**
   * 连接到图表 WebSocket
   */
  connectChart(chartId: string) {
    const token = localStorage.getItem('access_token');
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;

    this.url = `${protocol}//${host}/api/v1/ws/chart/${chartId}?token=${token}`;
    this.shouldReconnect = true;
    this._createConnection();
  }

  private _createConnection() {
    if (this.ws) {
      this.ws.close();
    }

    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      console.log('[WS] 已连接:', this.url);
    };

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        const { type, data } = msg;

        // 通知所有注册的处理器
        const handlers = this.handlers.get(type);
        if (handlers) {
          handlers.forEach((fn) => fn(data));
        }

        // 也通知 '*' 通配符处理器
        const wildcardHandlers = this.handlers.get('*');
        if (wildcardHandlers) {
          wildcardHandlers.forEach((fn) => fn(msg));
        }
      } catch (e) {
        console.error('[WS] 消息解析失败:', e);
      }
    };

    this.ws.onclose = (event) => {
      console.log('[WS] 已断开:', event.code, event.reason);
      if (this.shouldReconnect) {
        this._scheduleReconnect();
      }
    };

    this.ws.onerror = (error) => {
      console.error('[WS] 错误:', error);
    };
  }

  private _scheduleReconnect() {
    if (this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      console.log('[WS] 尝试重连...');
      this._createConnection();
    }, 3000);
  }

  /**
   * 注册消息处理器
   */
  on(type: string, handler: MessageHandler) {
    if (!this.handlers.has(type)) {
      this.handlers.set(type, new Set());
    }
    this.handlers.get(type)!.add(handler);
  }

  /**
   * 移除消息处理器
   */
  off(type: string, handler: MessageHandler) {
    this.handlers.get(type)?.delete(handler);
  }

  /**
   * 发送消息
   */
  send(type: string, data?: unknown) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type, data }));
    }
  }

  /**
   * 断开连接
   */
  disconnect() {
    this.shouldReconnect = false;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.ws?.close();
    this.ws = null;
    this.handlers.clear();
  }
}

// 单例
export const wsManager = new WSManager();
export default wsManager;
