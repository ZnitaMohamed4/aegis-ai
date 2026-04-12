import { Injectable } from '@angular/core';
import { webSocket, WebSocketSubject } from 'rxjs/webSocket';
import { Subject, Observable } from 'rxjs';
import { retry } from 'rxjs/operators';
import { Alert } from '../models/alert.model'; // We will use your models

export interface WebSocketAlertPayload {
  id: string;
  type?: 'alert' | 'log';
  sender: string;
  text: string;
  decision: string;
  primary_class: string;
  secondary_class: string | null;
  language?: string;
  m1_score: number;
  m2_confidence: number | null;
  llm_triggered?: boolean;
  llm_explanation?: string | null;
  severity: 'low' | 'medium' | 'high' | 'critical';
  timestamp: string;
}

@Injectable({
  providedIn: 'root'
})
export class AlertService {
  // The path to the Django Channels WebSocket we built
  private readonly WS_URL = 'ws://localhost:8000/ws/alerts/';
  
  // RxJS WebSocket hook
  private socket$!: WebSocketSubject<WebSocketAlertPayload>;
  
  // This acts as a loudspeaker. the service pushes data here, components listen.
  private alertStream = new Subject<WebSocketAlertPayload>();
  public alerts$ = this.alertStream.asObservable();

  constructor() {
    this.connect();
  }

  /**
   * Opens the WebSocket connection to Django and listens forever.
   */
  private connect(): void {
    if (!this.socket$ || this.socket$.closed) {
      this.socket$ = webSocket<WebSocketAlertPayload>(this.WS_URL);

      this.socket$.pipe(
        // If the Django server restarts, Angular will automatically try to reconnect every 5 seconds
        retry({ delay: 5000 })
      ).subscribe({
        next: (alertData) => {
          console.log('[AEGIS] 🚨 Real-Time WebSocket Alert Received:', alertData);
          // Broadcast the alert to any UI component that is listening
          this.alertStream.next(alertData);
        },
        error: (err) => console.error('[AEGIS] ❌ WebSocket Error:', err),
        complete: () => console.warn('[AEGIS] 🔌 WebSocket Disconnected')
      });
    }
  }
}
