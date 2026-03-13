import { Component, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DrawerModule } from 'primeng/drawer';
import { getRiskHex, getDecisionClass } from '@shared/utils/severity.utils';
import { MockAlert, MOCK_ALERTS } from './alerts.data';

@Component({
  selector: 'app-alerts',
  standalone: true,
  imports: [CommonModule, FormsModule, DrawerModule],
  templateUrl: './alerts.html',
  styleUrl: './alerts.css'
})
export class AlertsComponent {

  searchQuery = signal('');
  selectedSeverity = signal<string>('all');
  selectedDecision = signal<string>('all');
  selectedAlert = signal<MockAlert | null>(null);
  drawerVisible = signal(false);

  severityFilters = ['all', 'critical', 'high', 'medium', 'low'];
  decisionFilters = ['all', 'BLOCK', 'ESCALATE', 'WARN', 'ALLOW'];

  alerts = signal<MockAlert[]>(MOCK_ALERTS);

  filteredAlerts = computed(() => {
    return this.alerts().filter(alert => {
      const matchesSeverity = this.selectedSeverity() === 'all' || alert.severity === this.selectedSeverity();
      const matchesDecision = this.selectedDecision() === 'all' || alert.decision === this.selectedDecision();
      const matchesSearch = alert.preview.toLowerCase().includes(this.searchQuery().toLowerCase());
      return matchesSeverity && matchesDecision && matchesSearch;
    });
  });

  getRiskHex = getRiskHex;
  getDecisionClass = getDecisionClass;

  openDetail(alert: MockAlert) {
    this.selectedAlert.set(alert);
    this.drawerVisible.set(true);
  }

  markResolved(alert: MockAlert) {
    this.alerts.update(list =>
      list.map(a => a.id === alert.id ? { ...a, is_resolved: true } : a)
    );
  }

  formatDate(dateStr: string): string {
    const date = new Date(dateStr);
    return date.toLocaleTimeString('en', { hour: '2-digit', minute: '2-digit' }) +
      ' · ' + date.toLocaleDateString('en', { month: 'short', day: 'numeric' });
  }
}
