import { Component, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { DialogModule } from 'primeng/dialog';
import { ChartModule } from 'primeng/chart';
import { getRiskHex } from '@shared/utils/severity.utils';
import { RiskLevel, ChildProfile, ContactProfile, RiskSnapshot } from '@core/models';
import { ApiService } from '@core/services/api.service';

@Component({
  selector: 'app-risk-profiles',
  standalone: true,
  imports: [CommonModule, DialogModule, ChartModule],
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

  getTrendChart(trend: number[], level: RiskLevel) {
    const color = this.getChartColor(level);
    return {
      labels: ['D-6', 'D-5', 'D-4', 'D-3', 'D-2', 'D-1', 'Today'],
      datasets: [{
        data: trend,
        borderColor: color,
        backgroundColor: color + '22',
        fill: true,
        tension: 0.35,
        pointRadius: 3,
        pointHoverRadius: 5,
        borderWidth: 2
      }]
    };
  }

  trendOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { ticks: { color: '#94A3B8', font: { size: 10 } }, grid: { color: '#47556922' } },
      y: { min: 0, max: 1, ticks: { color: '#94A3B8', font: { size: 10 } }, grid: { color: '#47556922' } }
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

  ageFromBirthDate(date: string): number {
    const dob = new Date(date);
    const now = new Date();
    let age = now.getFullYear() - dob.getFullYear();
    const m = now.getMonth() - dob.getMonth();
    if (m < 0 || (m === 0 && now.getDate() < dob.getDate())) {
      age--;
    }
    return age;
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
}
