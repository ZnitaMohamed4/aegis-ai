import { Component, input, output, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DrawerModule } from 'primeng/drawer';
import { getRiskHex, getDecisionClass } from '@shared/utils/severity.utils';
import { MockAlert } from '@core/models';
import { SkeletonModule } from 'primeng/skeleton';
import { OnInit } from '@angular/core';

const PAGE_SIZE = 20;

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
  selectedCategory = signal<string>('all');
  selectedStatus = signal<string>('open'); // Default to open
  selectedAlert = signal<MockAlert | null>(null);
  drawerVisible = signal(false);
  visibleCount = signal(PAGE_SIZE);

  skeletonItems = [1, 2, 3, 4, 5];

  // No 'low' (ALLOW is not in the alerts list) and no 'ALLOW' in decisions
  severityFilters = ['all', 'critical', 'high', 'medium'];
  decisionFilters = ['all', 'BLOCK', 'ESCALATE', 'WARN', 'REVISE'];
  categoryFilters = [
    { label: 'All', value: 'all' },
    { label: 'Threat', value: 'threat' },
    { label: 'Sexual', value: 'sexual_harassment' },
    { label: 'Discrimination', value: 'discrimination' },
    { label: 'Verbal', value: 'verbal_harassment' },
  ];
  statusFilters = ['all', 'open', 'resolved'];

  filteredAlerts = computed(() => {
    const q = this.searchQuery().toLowerCase();
    const sev = this.selectedSeverity();
    const dec = this.selectedDecision();
    const cat = this.selectedCategory();
    const stat = this.selectedStatus();

    return this.alerts().filter(alert => {
      const matchesSeverity = sev === 'all' || alert.severity === sev;
      const matchesDecision = dec === 'all' || alert.decision === dec;
      const matchesCategory = cat === 'all' || (alert.category || '').replace(/ /g, '_') === cat;
      const matchesStatus = stat === 'all' || (stat === 'open' && !alert.is_resolved) || (stat === 'resolved' && alert.is_resolved);
      const matchesSearch = !q
        || alert.preview.toLowerCase().includes(q)
        || (alert.category || '').toLowerCase().includes(q);
      return matchesSeverity && matchesDecision && matchesCategory && matchesStatus && matchesSearch;
    });
  });

  /** Paginated slice shown in the table */
  visibleAlerts = computed(() => this.filteredAlerts().slice(0, this.visibleCount()));

  hasMore = computed(() => this.filteredAlerts().length > this.visibleCount());

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

  loadMore() {
    this.visibleCount.update(n => n + PAGE_SIZE);
  }

  resetPagination() {
    this.visibleCount.set(PAGE_SIZE);
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

  /** Truncate LLM explanation for the table cell (full text shown in drawer) */
  truncateExplanation(text: string | null, maxLen = 80): string {
    if (!text) return '';
    return text.length > maxLen ? text.substring(0, maxLen) + '…' : text;
  }
}
