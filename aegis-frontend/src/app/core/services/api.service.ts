import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

// This interface makes sure our code knows exactly what the data looks like
export interface DashboardStatsResponse {
  stats: {
    total_messages_today: number;
    total_alerts_today: number;
    total_blocked_today: number;
    pending_review: number;
    avg_latency_ms: number;
  };
  decision_breakdown: Record<string, number>;
  at_risk_users: any[];
}

@Injectable({
  providedIn: 'root'
})
export class ApiService {
  private readonly BASE_URL = 'http://localhost:8000/api/v1';

  constructor(private http: HttpClient) {}

  /**
   * Fetches the dashboard stats we just built in Django!
   */
  getDashboardStats(): Observable<DashboardStatsResponse> {
    return this.http.get<DashboardStatsResponse>(`${this.BASE_URL}/stats/dashboard/`);
  }
}
