import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

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
    evolution_api_online: boolean;
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
  private readonly BASE_URL = environment.apiBaseUrl;

  constructor(private http: HttpClient) {}

  // ════════════════════════════════════════════════════════════════
  // ADMIN ENDPOINTS (all data, unfiltered)
  // ════════════════════════════════════════════════════════════════

  /** Fetches the dashboard stats (admin — all data). */
  getDashboardStats(): Observable<DashboardStatsResponse> {
    return this.http.get<DashboardStatsResponse>(`${this.BASE_URL}/stats/dashboard/`);
  }

  /** Fetches the recent alerts history (admin — all data). */
  getAlerts(senderJid?: string): Observable<any[]> {
    let url = `${this.BASE_URL}/alerts/`;
    if (senderJid) {
      url += `?sender_jid=${encodeURIComponent(senderJid)}`;
    }
    return this.http.get<any[]>(url);
  }

  /** Resolves an alert */
  resolveAlert(id: string): Observable<any> {
    return this.http.post<any>(`${this.BASE_URL}/alerts/${id}/resolve/`, {});
  }

  /** Fetches the queue of items awaiting human review. */
  getReviewQueue(): Observable<any[]> {
    return this.http.get<any[]>(`${this.BASE_URL}/review/`);
  }

  /** Submits a human override decision and class label. */
  humanOverride(id: string, decision: string, label: string, note: string = ''): Observable<any> {
    return this.http.post<any>(`${this.BASE_URL}/review/${id}/override/`, { decision, label, note });
  }

  getReviewStats(): Observable<any> {
    return this.http.get<any>(`${this.BASE_URL}/review/stats/`);
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

  /** Fetches historical analytics aggregated for the dashboard. */
  getAdminAnalytics(range: '7D' | '30D'): Observable<any> {
    return this.http.get<any>(`${this.BASE_URL}/admin/analytics/?range=${range}`);
  }

  /** Fetches all risk profiles (children and contacts) across the platform. */
  getAdminRiskProfiles(): Observable<{children: any[], contacts: any[]}> {
    return this.http.get<{children: any[], contacts: any[]}>(`${this.BASE_URL}/admin/risk-profiles/`);
  }

  /** Fetches all monitored children with real IDs for report generation. */
  getAdminChildren(): Observable<any[]> {
    return this.http.get<any[]>(`${this.BASE_URL}/admin/children/`);
  }

  /** Fetches all channels/instances currently connected (monitoring dashboard). */
  getAdminChannels(): Observable<any> {
    return this.http.get<any>(`${this.BASE_URL}/admin/channels/`);
  }

  /** Force-disconnects/deletes a channel instance (emergency admin override). */
  deleteAdminChannel(instanceId: string): Observable<any> {
    return this.http.delete<any>(`${this.BASE_URL}/admin/channels/${instanceId}/`);
  }

  /** Updates the currently authenticated user's account details. */
  updateCurrentUser(payload: any): Observable<any> {
    return this.http.put<any>(`${this.BASE_URL}/auth/me/`, payload);
  }

  /** Fetches global platform settings (AI configuration, thresholds, retention). */
  getSystemSettings(): Observable<any> {
    return this.http.get<any>(`${this.BASE_URL}/admin/settings/`);
  }

  /** Updates global platform settings. */
  updateSystemSettings(payload: any): Observable<any> {
    return this.http.put<any>(`${this.BASE_URL}/admin/settings/`, payload);
  }

  /** Tests the LLM connection by pinging the configured provider. */
  testLlmConnection(): Observable<any> {
    return this.http.post<any>(`${this.BASE_URL}/admin/test-llm/`, {});
  }

  /** Runs a message through the real AI pipeline without persisting. */
  simulateMessage(text: string, language: string): Observable<any> {
    return this.http.post<any>(`${this.BASE_URL}/admin/simulate/`, { text, language });
  }

  /** Fetches live agent latencies from Redis. */
  getAgentLatencies(): Observable<any> {
    return this.http.get<any>(`${this.BASE_URL}/admin/agent-latencies/`);
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

  /** Fetches Digital Citizenship events (SelfModerationEvents) — scoped to the parent's child. */
  getDigitalCitizenship(): Observable<any> {
    return this.http.get<any>(`${this.BASE_URL}/parent/digital-citizenship/`);
  }

  /** Fetches emotional pattern heatmap data (day × time slot matrix). */
  getEmotionalHeatmap(range: number = 30): Observable<any> {
    return this.http.get<any>(`${this.BASE_URL}/parent/emotional-heatmap/?range=${range}`);
  }

  /** Fetches forensic evidence export data for legal documentation. */
  getForensicEvidence(days: number = 30): Observable<any> {
    return this.http.get<any>(`${this.BASE_URL}/parent/export-evidence/?days=${days}`);
  }
}
