import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

// ── Admin Dashboard Stats Response ──
export interface DashboardStatsResponse {
  stats: {
    total_messages_today: number;
    total_alerts_today: number;
    total_blocked_today: number;
    llm_interventions: number;
    avg_latency_ms: number;
    latencies: {
      agent_1: number;
      agent_2: number;
      agent_3: number;
      agent_4: number;
      agent_5: number;
    };
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

// ── Parent Dashboard Stats Response ──
export interface ParentChildInfo {
  id: string;
  name: string;
  whatsapp_jid: string;
  display_number: string;
  risk_level: string;
  is_monitored: boolean;
}

export interface ParentDashboardStatsResponse {
  child: ParentChildInfo | null;
  stats: {
    total_messages_today: number;
    total_alerts_today: number;
    total_blocked_today: number;
    total_messages_all_time: number;
    total_alerts_all_time: number;
    total_blocked_all_time: number;
    llm_interventions: number;
    avg_latency_ms: number;
  };
  category_breakdown: Record<string, number>;
  weekly_activity: { day: string; blocked: number; warned: number; safe: number }[];
  at_risk_contacts: any[];
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

  // ════════════════════════════════════════════════════════════════
  // ADMIN ENDPOINTS (all data, unfiltered)
  // ════════════════════════════════════════════════════════════════

  /** Fetches the dashboard stats (admin — all data). */
  getDashboardStats(): Observable<DashboardStatsResponse> {
    return this.http.get<DashboardStatsResponse>(`${this.BASE_URL}/stats/dashboard/`);
  }

  /** Fetches the recent alerts history (admin — all data). */
  getAlerts(): Observable<any[]> {
    return this.http.get<any[]>(`${this.BASE_URL}/alerts/`);
  }

  /** Fetches the queue of items awaiting human review. */
  getReviewQueue(): Observable<any[]> {
    return this.http.get<any[]>(`${this.BASE_URL}/review/`);
  }

  /** Submits a human override decision and class label. */
  humanOverride(id: string, decision: string, label: string, note: string = ''): Observable<any> {
    return this.http.post<any>(`${this.BASE_URL}/review/${id}/override/`, { decision, label, note });
  }

  /** Flags an existing message for human review. */
  flagForReview(id: string): Observable<any> {
    return this.http.post<any>(`${this.BASE_URL}/review/${id}/flag/`, {});
  }

  /** Fetches the last 20 moderation events (ALL decisions incl. ALLOW). */
  getActivityFeed(): Observable<any[]> {
    return this.http.get<any[]>(`${this.BASE_URL}/activity/`);
  }

  /** Fetches all parent users and their monitored children for the admin system. */
  getAdminUsers(): Observable<any[]> {
    return this.http.get<any[]>(`${this.BASE_URL}/admin/users/`);
  }

  /** Creates a new parent user from the admin dashboard (child optional). */
  createAdminUser(payload: any): Observable<any> {
    return this.http.post<any>(`${this.BASE_URL}/admin/users/`, payload);
  }

  /** Deletes a parent user. */
  deleteAdminUser(userId: string): Observable<any> {
    return this.http.delete<any>(`${this.BASE_URL}/admin/users/${userId}/`);
  }

  /** Fetches all conversations across the entire platform. */
  getAdminConversations(): Observable<{contacts: any[], messages: Record<string, any[]>}> {
    return this.http.get<{contacts: any[], messages: Record<string, any[]>}>(`${this.BASE_URL}/admin/conversations/`);
  }

  /** Fetches all risk profiles (children and contacts) across the platform. */
  getAdminRiskProfiles(): Observable<{children: any[], contacts: any[]}> {
    return this.http.get<{children: any[], contacts: any[]}>(`${this.BASE_URL}/admin/risk-profiles/`);
  }

  // ════════════════════════════════════════════════════════════════
  // PARENT ENDPOINTS (filtered to logged-in parent's child only)
  // ════════════════════════════════════════════════════════════════

  /** Fetches parent dashboard stats — scoped to their child only. */
  getParentDashboardStats(): Observable<ParentDashboardStatsResponse> {
    return this.http.get<ParentDashboardStatsResponse>(`${this.BASE_URL}/parent/stats/`);
  }

  /** Fetches alerts — scoped to the parent's child only. */
  getParentAlerts(): Observable<any[]> {
    return this.http.get<any[]>(`${this.BASE_URL}/parent/alerts/`);
  }

  /** Fetches activity feed — scoped to the parent's child only. */
  getParentActivityFeed(): Observable<any[]> {
    return this.http.get<any[]>(`${this.BASE_URL}/parent/activity/`);
  }
  /** Fetches blocked messages — scoped to the parent's child only. */
  getParentBlockedMessages(): Observable<any[]> {
    return this.http.get<any[]>(`${this.BASE_URL}/parent/blocked-messages/`);
  }

  /** Fetches conversations — scoped to the parent's child only. */
  getParentConversations(): Observable<any> {
    return this.http.get<any>(`${this.BASE_URL}/parent/conversations/`);
  }

  /** Fetches risk profile — scoped to the parent's child only. */
  getParentRiskProfile(): Observable<any> {
    return this.http.get<any>(`${this.BASE_URL}/parent/risk-profile/`);
  }
}

