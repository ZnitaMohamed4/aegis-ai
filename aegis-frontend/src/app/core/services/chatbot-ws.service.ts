import { Injectable } from '@angular/core';
import { webSocket, WebSocketSubject } from 'rxjs/webSocket';
import { Subject, Observable } from 'rxjs';
import { retry } from 'rxjs/operators';
import { environment } from '../../../environments/environment';

export interface ProactiveAlertPayload {
  type: 'proactive_alert';
  alert_id: string;
  session_id: string;
  message_id: string;
  content: string;
  trigger_count: number;
  categories: string[];
  timestamp: string;
}

@Injectable({
  providedIn: 'root'
})
export class ChatbotWsService {
  /**
   * WebSocket connection for proactive chatbot alerts.
   * Connects to ws://localhost:8000/ws/chatbot/?token=<JWT>
   * Receives real-time proactive alert messages from the backend.
   */
  private get WS_URL(): string {
    const token = localStorage.getItem('access_token');
    const base = environment.wsBaseUrl || `ws://${window.location.host}`;
    return `${base}/ws/chatbot/?token=${token}`;
  }

  private socket$!: WebSocketSubject<ProactiveAlertPayload>;
  private proactiveStream = new Subject<ProactiveAlertPayload>();
  public proactiveAlerts$ = this.proactiveStream.asObservable();

  private isConnected = false;

  constructor() {
    // Don't auto-connect — only connect when chatbot page is active
  }

  /**
   * Connect to the chatbot WebSocket.
   * Call this from the chatbot page's ngOnInit.
   */
  connect(): void {
    if (this.isConnected) return;

    try {
      this.socket$ = webSocket<ProactiveAlertPayload>(this.WS_URL);

      this.socket$.pipe(
        retry({ delay: 5000 })
      ).subscribe({
        next: (data) => {
          console.log('[AEGIS-CHATBOT] Proactive alert received:', data);
          this.proactiveStream.next(data);
        },
        error: (err) => console.error('[AEGIS-CHATBOT] WebSocket error:', err),
        complete: () => console.warn('[AEGIS-CHATBOT] WebSocket disconnected')
      });

      this.isConnected = true;
    } catch (err) {
      console.error('[AEGIS-CHATBOT] Failed to connect WebSocket:', err);
    }
  }

  /**
   * Disconnect from the chatbot WebSocket.
   * Call this from the chatbot page's ngOnDestroy.
   */
  disconnect(): void {
    if (this.socket$ && !this.socket$.closed) {
      this.socket$.complete();
    }
    this.isConnected = false;
  }
}
