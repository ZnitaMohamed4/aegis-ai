import { Component, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DrawerModule } from 'primeng/drawer';
import { ReportCardComponent } from '@shared/index';
import { MOCK_REPORTS } from './reports.data';
import { ReportStatus, ReportType, Report } from '@core/models';

@Component({
  selector: 'app-reports',
  standalone: true,
  imports: [CommonModule, FormsModule, DrawerModule, ReportCardComponent],
  templateUrl: './reports.html',
  styleUrl: './reports.css'
})
export class ReportsComponent {
  requestDrawerVisible = signal(false);

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
  }

  setReportType(type: string) {
    this.requestForm.update(f => ({ ...f, report_type: type as ReportType }));
  }
}
