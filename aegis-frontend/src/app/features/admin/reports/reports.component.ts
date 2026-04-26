import { Component, signal, computed, inject, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DrawerModule } from 'primeng/drawer';
import { ReportCardComponent } from '@shared/index';
import { ReportStatus, ReportType, Report, DeliveryChannel } from '@core/models';
import { ReportService } from '@core/services/report.service';
import { ApiService } from '@core/services/api.service';

interface ChildOption {
  id: string;
  name: string;
}

@Component({
  selector: 'app-reports',
  standalone: true,
  imports: [CommonModule, FormsModule, DrawerModule, ReportCardComponent],
  templateUrl: './reports.html',
  styleUrl: './reports.css'
})
export class AdminReportsComponent implements OnInit, OnDestroy {
  private reportService = inject(ReportService);
  private apiService = inject(ApiService);
  private pollInterval: any;

  requestDrawerVisible = signal(false);
  isGenerating = signal(false);
  children = signal<ChildOption[]>([]);

  requestForm = signal({
    child_id: '',
    period_start: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    period_end: new Date().toISOString().split('T')[0],
    report_type: 'intelligence' as ReportType,
    delivery_channel: 'dashboard' as DeliveryChannel
  });

  filterStatus = signal<string>('all');
  filterType = signal<string>('all');

  reports = signal<Report[]>([]);

  // Precomputed stats
  totalCount = computed(() => this.reports().length);
  readyCount = computed(() => this.reports().filter(r => r.status === 'ready').length);
  generatingCount = computed(() => this.reports().filter(r => r.status === 'generating').length);
  legalCount = computed(() => this.reports().filter(r => r.flagged_legal).length);

  filteredReports = computed(() =>
    this.reports().filter(r => {
      const matchStatus = this.filterStatus() === 'all' || r.status === this.filterStatus();
      const matchType = this.filterType() === 'all' || r.report_type === this.filterType();
      return matchStatus && matchType;
    })
  );

  ngOnInit() {
    this.loadReports();
    this.loadChildren();
    this.startPolling();
  }

  ngOnDestroy() {
    if (this.pollInterval) clearInterval(this.pollInterval);
  }

  startPolling() {
    this.pollInterval = setInterval(() => {
      if (this.reports().some(r => r.status === 'generating')) {
        this.reportService.getAdminReports().subscribe({
          next: (data) => this.reports.set(data)
        });
      }
    }, 4000);
  }

  loadReports() {
    this.reportService.getAdminReports().subscribe({
      next: (data) => this.reports.set(data),
      error: (err) => console.error('Failed to load admin reports', err)
    });
  }

  loadChildren() {
    // Fetch children list from admin users endpoint for the dropdown
    this.apiService.getAdminUsers().subscribe({
      next: (users: any[]) => {
        const childList: ChildOption[] = [];
        for (const user of users) {
          if (user.linked_child) {
            childList.push({
              id: user.id,
              name: `${user.linked_child.identifier} (${user.full_name})`
            });
          }
        }
        this.children.set(childList);
      },
      error: () => {} // Non-critical, dropdown will just show "All Children"
    });
  }

  openRequest() {
    this.requestDrawerVisible.set(true);
  }

  submitRequest() {
    if (this.isGenerating()) return;
    this.isGenerating.set(true);
    this.requestDrawerVisible.set(false);

    const payload = this.requestForm();
    this.reportService.generateReport(payload).subscribe({
      next: () => {
        this.isGenerating.set(false);
        this.loadReports();
      },
      error: (err) => {
        this.isGenerating.set(false);
        console.error('Failed to trigger report', err);
      }
    });
  }

  toggleLegal(report: Report) {
    this.reports.update(list =>
      list.map(r => r.id === report.id ? { ...r, flagged_legal: !r.flagged_legal } : r)
    );
  }

  setReportType(type: string) {
    this.requestForm.update(f => ({ ...f, report_type: type as ReportType }));
  }

  setDeliveryChannel(channel: string) {
    this.requestForm.update(f => ({ ...f, delivery_channel: channel as DeliveryChannel }));
  }
}
