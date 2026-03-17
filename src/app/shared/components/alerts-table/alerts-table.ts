import { Component, input, output, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DrawerModule } from 'primeng/drawer';
import { getRiskHex, getDecisionClass } from '@shared/utils/severity.utils';
import { MockAlert } from '@core/models';
import { SkeletonModule } from 'primeng/skeleton';
import { OnInit } from '@angular/core';

@Component({
  selector: 'app-alerts-table',
  standalone: true,
  imports: [CommonModule, FormsModule, DrawerModule, SkeletonModule],
  templateUrl: './alerts-table.html',
  styleUrl: './alerts-table.css'
})
export class AlertsTableComponent implements OnInit {
  alerts = input.required<MockAlert[]>();
  resolve = output<MockAlert>();

  isLoading = signal(true);
  searchQuery = signal('');
  selectedSeverity = signal<string>('all');
  selectedDecision = signal<string>('all');
  selectedAlert = signal<MockAlert | null>(null);
  drawerVisible = signal(false);

  skeletonItems = [1, 2, 3, 4, 5];

  severityFilters = ['all', 'critical', 'high', 'medium', 'low'];
  decisionFilters = ['all', 'BLOCK', 'ESCALATE', 'WARN', 'ALLOW'];

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
    this.resolve.emit(alert);
    this.drawerVisible.set(false);
  }

  ngOnInit() {
    setTimeout(() => {
      this.isLoading.set(false);
    }, 800);
  }

  formatDate(dateStr: string): string {
    const date = new Date(dateStr);
    return date.toLocaleTimeString('en', { hour: '2-digit', minute: '2-digit' }) +
      ' · ' + date.toLocaleDateString('en', { month: 'short', day: 'numeric' });
  }
}
