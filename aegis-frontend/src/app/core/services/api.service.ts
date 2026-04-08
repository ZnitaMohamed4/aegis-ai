import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

// This interface makes sure our code knows exactly what the data looks like
export interface DashboardStatsResponse {
  stats: {
    total_messages_today: number;
    total_alerts_today: number;
    total_blocked_today: number;
    llm_interventions: number;
    avg_latency_ms: number;
  };
  category_breakdown: Record<string, number>;
  weekly_activity: { day: string; blocked: number; warned: number; safe: number }[];
  at_risk_users: any[];
  hourly_activity: {
    labels: string[];
    threats: number[];
    safe: number[];
  };
  language_distribution: {
    labels: string[];
    data: number[];
  };
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

  /**
   * Fetches the recent alerts history
   */
  getAlerts(): Observable<any[]> {
    return this.http.get<any[]>(`${this.BASE_URL}/alerts/`);
  }

  /**
   * Fetches the LLM Audit log
   */
  getLLMAudits(): Observable<any[]> {
    return this.http.get<any[]>(`${this.BASE_URL}/audits/llm/`);
  }

  /**
   * Overrides an LLM Decision
   */
  overrideLLMDecision(id: string, decision: 'ALLOW' | 'BLOCK'): Observable<any> {
    return this.http.post<any>(`${this.BASE_URL}/audits/llm/${id}/override/`, { decision });
  }
}

