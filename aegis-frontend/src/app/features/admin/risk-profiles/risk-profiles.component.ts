import { Component, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { DialogModule } from 'primeng/dialog';
import { ChartModule } from 'primeng/chart';
import { getRiskHex } from '@shared/utils/severity.utils';
import { WhatsappJidPipe } from '@shared/pipes/whatsapp-jid.pipe';
import { RiskLevel, ChildProfile, ContactProfile, RiskSnapshot } from '@core/models';
import { ApiService } from '@core/services/api.service';

interface CategoryEntry {
  key: string;
  count: number;
}

@Component({
  selector: 'app-risk-profiles',
  standalone: true,
  imports: [CommonModule, DialogModule, ChartModule, WhatsappJidPipe],
  templateUrl: './risk-profiles.html',
  styleUrl: './risk-profiles.css'
})
export class RiskProfilesComponent implements OnInit {

  activeTab = signal<'children' | 'contacts'>('children');
  childDialogVisible = signal(false);
  contactDialogVisible = signal(false);
  showClusterDetails = signal(false);
  selectedChild = signal<ChildProfile | null>(null);
  selectedContact = signal<ContactProfile | null>(null);

  children = signal<ChildProfile[]>([]);
  contacts = signal<ContactProfile[]>([]);

  getRiskHex = getRiskHex;

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private api: ApiService
  ) {}

  ngOnInit() {
    this.api.getAdminRiskProfiles().subscribe({
      next: (data) => {
        this.children.set(data.children);
        this.contacts.set(data.contacts);

        // Re-process route params after data is loaded
        this.route.queryParamMap.subscribe(params => {
          const tab = params.get('tab');
          const childId = params.get('child');
          const contactId = params.get('contact');

          if (tab === 'children' || tab === 'contacts') {
            this.activeTab.set(tab);
          }

          if (childId) {
            const child = this.children().find(c => c.id === childId);
            if (child) {
              this.openChild(child);
              this.activeTab.set('children');
            }
          }

          if (contactId) {
            const contact = this.contacts().find(c => c.id === contactId);
            if (contact) {
              this.openContact(contact);
              this.activeTab.set('contacts');
            }
          }
        });
      },
      error: (err) => console.error('Failed to load risk profiles:', err)
    });
  }

  // ── Chart builders ───────────────────────────────────
  getChartColor(level: RiskLevel): string {
    const map: Record<RiskLevel, string> = {
      low: '#10D9A0',
      medium: '#FFB020',
      high: '#FF7A30',
      critical: '#FF4D4D'
    };
    return map[level];
  }

  getArchetypeColor(archetype: string): string {
    const map: Record<string, string> = {
      'Normal User': '#10D9A0',
      'Troll Pattern': '#8b5cf6',
      'Bully Pattern': '#f59e0b',
      'Groomer Pattern': '#f43f5e'
    };
    return map[archetype] || '#94A3B8';
  }

  getArchetypeIcon(archetype: string): string {
    const map: Record<string, string> = {
      'Normal User': 'pi-check-circle',
      'Troll Pattern': 'pi-comment',
      'Bully Pattern': 'pi-bolt',
      'Groomer Pattern': 'pi-eye'
    };
    return map[archetype] || 'pi-question-circle';
  }

  getTrendChart(trend: number[], level: RiskLevel) {
    const color = this.getChartColor(level);
    const labels = trend.map((_, i) => {
      const offset = trend.length - 1 - i;
      return offset === 0 ? 'Today' : `D-${offset}`;
    });

    return {
      labels: labels,
      datasets: [{
        data: trend,
        borderColor: color,
        backgroundColor: color + '22',
        fill: true,
        tension: 0.4,
        pointRadius: 4,
        pointHoverRadius: 6,
        borderWidth: 3,
        pointBackgroundColor: color,
        pointBorderColor: '#fff',
        pointBorderWidth: 2
      }]
    };
  }

  trendOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { 
      legend: { display: false },
      tooltip: {
        backgroundColor: 'rgba(15, 23, 42, 0.9)',
        titleFont: { size: 11, weight: 'bold' },
        bodyFont: { size: 12 },
        padding: 10,
        cornerRadius: 8,
        displayColors: false
      }
    },
    scales: {
      x: { 
        ticks: { color: '#94A3B8', font: { size: 9, weight: '600' } }, 
        grid: { display: false } 
      },
      y: { 
        min: 0, 
        max: 1, 
        ticks: { 
          color: '#94A3B8', 
          font: { size: 9 },
          callback: (value: any) => (value * 100).toFixed(0) + '%'
        }, 
        grid: { color: 'rgba(148, 163, 184, 0.1)', borderDash: [4, 4] } 
      }
    }
  };

  // ── Actions ──────────────────────────────────────────
  openChild(child: ChildProfile) {
    this.selectedChild.set(child);
    this.selectedContact.set(null);
    this.contactDialogVisible.set(false);
    this.childDialogVisible.set(true);
    this.showClusterDetails.set(false);
  }

  openContact(contact: ContactProfile) {
    this.selectedContact.set(contact);
    this.selectedChild.set(null);
    this.childDialogVisible.set(false);
    this.contactDialogVisible.set(true);
  }

  goToChildConversations(child: ChildProfile) {
    this.router.navigate(['/admin/conversations'], {
      queryParams: { child: child.id }
    });
  }

  goToParentUser(child: ChildProfile) {
    this.router.navigate(['/admin/users'], {
      queryParams: { parent: child.parent_user_id }
    });
  }

  goToReports(childId?: string) {
    this.router.navigate(['/admin/reports'], {
      queryParams: childId ? { child: childId } : undefined
    });
  }

  goToAlertsByContact(contact: ContactProfile) {
    this.router.navigate(['/admin/alerts'], {
      queryParams: { jid: contact.raw_jid }
    });
  }

  goToAlert(alertId: string) {
    this.router.navigate(['/admin/alerts'], {
      queryParams: { alert: alertId }
    });
  }

  goToConversationsForContact(contact: ContactProfile) {
    this.router.navigate(['/admin/conversations'], {
      queryParams: { chat: contact.raw_jid }
    });
  }

  // ── Helpers ──────────────────────────────────────────
  pct(value: number): string {
    return `${(value * 100).toFixed(1)}%`;
  }

  barW(value: number, max = 1): string {
    return `${Math.min((value / max) * 100, 100)}%`;
  }

  getRiskTrendDirection(trend: number[]): 'up' | 'down' | 'flat' {
    if (trend.length < 2) return 'flat';
    const delta = trend[trend.length - 1] - trend[trend.length - 2];
    if (delta > 0.01) return 'up';
    if (delta < -0.01) return 'down';
    return 'flat';
  }

  getRiskTrendDelta(trend: number): string {
    return trend >= 0 ? `+${trend.toFixed(2)}` : trend.toFixed(2);
  }

  getRiskTrendChange(trend: number[]): number {
    if (trend.length < 2) return 0;
    return trend[trend.length - 1] - trend[trend.length - 2];
  }

  ageFromBirthDate(date: string): number | string {
    if (!date) return 'N/A';
    const dob = new Date(date);
    if (isNaN(dob.getTime())) return 'N/A';
    const now = new Date();
    let age = now.getFullYear() - dob.getFullYear();
    const m = now.getMonth() - dob.getMonth();
    if (m < 0 || (m === 0 && now.getDate() < dob.getDate())) {
      age--;
    }
    return age;
  }

  formatDate(isoDate: string): string {
    if (!isoDate) return 'N/A';
    const d = new Date(isoDate);
    if (isNaN(d.getTime())) return isoDate; // Already formatted
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }

  timeAgo(isoDate: string): string {
    if (!isoDate) return 'N/A';
    const d = new Date(isoDate);
    if (isNaN(d.getTime())) return isoDate;
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const mins = Math.floor(diffMs / 60000);
    if (mins < 1) return 'Just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    return `${days}d ago`;
  }

  getRiskSpikes(snapshots: RiskSnapshot[]): RiskSnapshot[] {
    const spikes: RiskSnapshot[] = [];
    for (let i = 1; i < snapshots.length; i++) {
      const jump = snapshots[i].score_risque_snapshot - snapshots[i - 1].score_risque_snapshot;
      if (jump >= 0.12 && snapshots[i].alert_id) {
        spikes.push(snapshots[i]);
      }
    }
    return spikes;
  }

  /** Get threat contacts that target a specific child */
  getChildThreats(child: ChildProfile): ContactProfile[] {
    return this.contacts()
      .filter(c => c.related_child_ids.includes(child.id))
      .sort((a, b) => b.threat_score - a.threat_score)
      .slice(0, 5);
  }

  /** Get the max count in a category breakdown for proportional bar widths */
  getMaxCategoryCount(breakdown: Record<string, number>): number {
    const values = Object.values(breakdown || {});
    return values.length > 0 ? Math.max(...values) : 1;
  }

  getSharedSuspiciousContacts(childA: ChildProfile, childB: ChildProfile): ContactProfile[] {
    return this.contacts().filter(contact =>
      contact.related_child_ids.includes(childA.id) &&
      contact.related_child_ids.includes(childB.id)
    );
  }

  getAffectedSchoolChildren(child: ChildProfile): Array<{ child: ChildProfile; sharedContacts: ContactProfile[] }> {
    return this.children()
      .filter(c => c.id !== child.id && c.nom_ecole === child.nom_ecole)
      .map(peer => ({
        child: peer,
        sharedContacts: this.getSharedSuspiciousContacts(child, peer)
      }))
      .filter(item => item.sharedContacts.length > 0);
  }

  getClusterSignal(child: ChildProfile): {
    sameSchoolCount: number;
    sharedContactCount: number;
    severity: 'none' | 'amber' | 'red' | 'banner';
  } {
    const sameSchoolCount = this.schoolClusterCount(child.nom_ecole);
    const sharedContactCount = this.getAffectedSchoolChildren(child).length;

    if (sameSchoolCount < 2) {
      return { sameSchoolCount, sharedContactCount, severity: 'none' };
    }

    if (sharedContactCount >= 2) {
      return { sameSchoolCount, sharedContactCount, severity: 'banner' };
    }

    if (sharedContactCount >= 1) {
      return { sameSchoolCount, sharedContactCount, severity: 'red' };
    }

    return { sameSchoolCount, sharedContactCount, severity: 'amber' };
  }

  toggleClusterDetails() {
    this.showClusterDetails.update(v => !v);
  }

  schoolClusterCount(school: string): number {
    return this.children().filter(c => c.nom_ecole === school).length;
  }

  getCategoryEntries(breakdown: Record<string, number>): CategoryEntry[] {
    if (!breakdown) return [];
    return Object.entries(breakdown)
      .map(([key, count]) => ({ key, count }))
      .sort((a, b) => b.count - a.count);
  }

  /** Format category key for display: 'verbal_harassment' -> 'Verbal Harassment' */
  formatCategoryLabel(key: string): string {
    return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  }
}
