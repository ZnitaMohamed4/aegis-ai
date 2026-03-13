import { Component, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DrawerModule } from 'primeng/drawer';
import { getThreatHex } from '@shared/utils/severity.utils';
import { ReportStatus, ReportType, Report, MOCK_REPORTS } from './reports.data';

@Component({
  selector: 'app-reports',
  standalone: true,
  imports: [CommonModule, FormsModule, DrawerModule],
  templateUrl: './reports.html',
  styleUrl: './reports.css'
})
export class ReportsComponent {

  drawerVisible = signal(false);
  requestDrawerVisible = signal(false);
  selectedReport = signal<Report | null>(null);

  requestForm = signal({
    child_identifier: 'Child #A1',
    period_start: '2026-03-01',
    period_end: '2026-03-11',
    report_type: 'full' as ReportType
  });

  filterStatus = signal<string>('all');
  filterType = signal<string>('all');

  reports = signal<Report[]>(MOCK_REPORTS);

  filteredReports = computed(() =>
    this.reports().filter(r => {
      const matchStatus = this.filterStatus() === 'all' || r.status === this.filterStatus();
      const matchType = this.filterType() === 'all' || r.report_type === this.filterType();
      return matchStatus && matchType;
    })
  );

  getThreatHex = getThreatHex;

  openReport(report: Report) {
    this.selectedReport.set(report);
    this.drawerVisible.set(true);
  }

  openRequest() {
    this.requestDrawerVisible.set(true);
  }

  submitRequest() {
    const form = this.requestForm();
    const newReport: Report = {
      id: `RPT-00${this.reports().length + 1}`,
      child_identifier: form.child_identifier,
      requested_by: 'Admin',
      report_type: form.report_type,
      period_start: form.period_start,
      period_end: form.period_end,
      status: 'generating',
      flagged_legal: false,
      requested_at: 'Just now',
      ai_narrative: '',
      stats: {
        total_messages: 0, total_blocked: 0, unique_harassers: 0,
        escalations: 0, dominant_category: '-',
        risk_score_start: 0, risk_score_end: 0
      },
      threat_actors: []
    };

    this.reports.update(list => [newReport, ...list]);
    this.requestDrawerVisible.set(false);

    setTimeout(() => {
      this.reports.update(list =>
        list.map(r => r.id === newReport.id ? { ...r, status: 'ready' as ReportStatus } : r)
      );
    }, 4000);
  }

  toggleLegal(report: Report) {
    this.reports.update(list =>
      list.map(r => r.id === report.id ? { ...r, flagged_legal: !r.flagged_legal } : r)
    );
    this.selectedReport.update(r => r ? { ...r, flagged_legal: !r.flagged_legal } : r);
  }

  getTypeConfig(type: ReportType) {
    const map = {
      summary: { label: 'Summary', color: 'var(--accent)', bg: 'var(--accent-subtle)' },
      full: { label: 'Full Analysis', color: 'var(--accent)', bg: 'var(--accent-subtle)' },
      legal: { label: 'Legal Evidence', color: 'var(--critical)', bg: 'rgba(255, 77, 77, 0.14)' }
    };
    return map[type];
  }

  getStatusConfig(status: ReportStatus) {
    const map = {
      ready: { label: 'Ready', color: 'var(--low)', bg: 'rgba(16, 217, 160, 0.14)', icon: 'pi-check-circle' },
      generating: { label: 'Generating...', color: 'var(--medium)', bg: 'rgba(255, 176, 32, 0.14)', icon: 'pi-spin pi-spinner' },
      pending: { label: 'Pending', color: 'var(--text-secondary)', bg: 'rgba(122, 156, 201, 0.15)', icon: 'pi-clock' }
    };
    return map[status];
  }

  setReportType(type: string) {
    this.requestForm.update(f => ({ ...f, report_type: type as ReportType }));
  }
}
