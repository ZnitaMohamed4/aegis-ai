import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { ApiService } from '@core/services/api.service';

interface CitizenshipEvent {
  type: 'intervention';
  id: string;
  created_at: string;
  category: string;
  category_label: string;
  original_severity: string;
  message_deleted: boolean;
  educational_dm_sent: boolean;
  educational_dm_text: string;
  parent_notified: boolean;
  parenting_tip: string;
}

interface BotSession {
  type: 'bot_session';
  id: string;
  created_at: string;
  last_activity: string;
  message_count: number;
  has_safety_alert: boolean;
  threat_intel: {
    threat_type: string;
    perpetrator: string;
    location: string;
    urgency: string;
    summary: string;
  } | null;
}

type TimelineItem = CitizenshipEvent | BotSession;

interface CitizenshipSummary {
  total_events: number;
  messages_deleted: number;
  educational_dms_sent: number;
  category_breakdown: Record<string, number>;
  total_bot_sessions: number;
  total_safety_alerts: number;
}

@Component({
  selector: 'app-digital-citizenship',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './digital-citizenship.html',
  styleUrl: './digital-citizenship.css'
})
export class DigitalCitizenshipComponent implements OnInit {
  private apiService = inject(ApiService);

  loading = true;
  timeline: TimelineItem[] = [];
  summary: CitizenshipSummary | null = null;
  expandedTip: string | null = null;  // ID of the event whose tip is expanded

  readonly CATEGORY_ICONS: Record<string, string> = {
    verbal_harassment: 'pi-comment',
    threat: 'pi-exclamation-triangle',
    sexual_harassment: 'pi-shield',
    discrimination: 'pi-ban',
    repeated_messages: 'pi-replay',
    identity_theft: 'pi-user-minus',
    unknown: 'pi-question-circle',
  };

  readonly CATEGORY_COLORS: Record<string, string> = {
    verbal_harassment: '#FF7A30',
    threat: '#FF4D4D',
    sexual_harassment: '#A78BFA',
    discrimination: '#60A5FA',
    repeated_messages: '#FBBF24',
    identity_theft: '#F472B6',
    unknown: '#94A3B8',
  };

  readonly SEVERITY_LABELS: Record<string, string> = {
    BLOCK: 'Blocked',
    ESCALATE: 'Critical',
    WARN: 'Warning',
    REVISE: 'Reviewed',
    ALLOW: 'Cleared',
  };

  ngOnInit() {
    this.apiService.getDigitalCitizenship().subscribe({
      next: (data: any) => {
        this.summary = data.summary;
        this.timeline = data.timeline;
        this.loading = false;
      },
      error: (err) => {
        console.error('[AEGIS] Failed to load digital citizenship data:', err);
        this.loading = false;
      }
    });
  }

  getCategoryIcon(category: string): string {
    return this.CATEGORY_ICONS[category] ?? 'pi-question-circle';
  }

  getCategoryColor(category: string): string {
    return this.CATEGORY_COLORS[category] ?? '#94A3B8';
  }

  getSeverityLabel(severity: string): string {
    return this.SEVERITY_LABELS[severity] ?? severity;
  }

  formatDate(dateStr: string): string {
    const d = new Date(dateStr);
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' })
      + ' · '
      + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  toggleTip(id: string) {
    this.expandedTip = this.expandedTip === id ? null : id;
  }

  getTopCategories(): { label: string; count: number; color: string }[] {
    if (!this.summary) return [];
    return Object.entries(this.summary.category_breakdown)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 4)
      .map(([cat, count]) => ({
        label: cat.replace(/_/g, ' '),
        count,
        color: this.getCategoryColor(cat)
      }));
  }

  isIntervention(item: TimelineItem): item is CitizenshipEvent {
    return item.type === 'intervention';
  }

  isBotSession(item: TimelineItem): item is BotSession {
    return item.type === 'bot_session';
  }
}
