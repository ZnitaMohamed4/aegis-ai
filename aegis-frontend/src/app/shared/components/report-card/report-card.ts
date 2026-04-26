import { Component, input, output, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DrawerModule } from 'primeng/drawer';
import { RouterModule } from '@angular/router';
import { getThreatHex } from '@shared/utils/severity.utils';
import { ReportStatus, ReportType, Report } from '@core/models';
import { SkeletonModule } from 'primeng/skeleton';
import { OnInit, inject } from '@angular/core';
import { ReportService } from '@core/services/report.service';

@Component({
  selector: 'app-report-card',
  standalone: true,
  imports: [CommonModule, DrawerModule, RouterModule, SkeletonModule],
  templateUrl: './report-card.html',
  styleUrl: './report-card.css'
})
export class ReportCardComponent implements OnInit {
  reports = input.required<Report[]>();
  isAdmin = input<boolean>(false);
  toggleLegalEvent = output<Report>();
  
  private reportService = inject(ReportService);

  drawerVisible = signal(false);
  selectedReport = signal<Report | null>(null);
  displayedNarrative = signal('');
  private typeInterval: any;

  isLoading = signal(true);
  skeletonItems = [1, 2, 3];

  getThreatHex = getThreatHex;

  openReport(report: Report) {
    this.selectedReport.set(report);
    this.drawerVisible.set(true);
    this.animateNarrative(report.ai_narrative);
  }

  closeDrawer() {
    this.drawerVisible.set(false);
    if (this.typeInterval) clearInterval(this.typeInterval);
  }

  onToggleLegal(report: Report) {
    this.toggleLegalEvent.emit(report);
  }

  animateNarrative(text: string) {
    this.displayedNarrative.set('');
    if (this.typeInterval) clearInterval(this.typeInterval);
    if (!text) return;
    
    let i = 0;
    this.typeInterval = setInterval(() => {
      this.displayedNarrative.update(n => n + text[i]);
      i++;
      if (i >= text.length) clearInterval(this.typeInterval);
    }, 18);
  }

  getTypeConfig(type: ReportType) {
    const map: any = {
      summary: { label: 'Summary', color: 'var(--accent)', bg: 'var(--accent-subtle)' },
      full: { label: 'Full Analysis', color: 'var(--accent)', bg: 'var(--accent-subtle)' },
      legal: { label: 'Legal Evidence', color: 'var(--critical)', bg: 'rgba(255, 77, 77, 0.14)' },
      intelligence: { label: 'Intelligence Brief', color: 'var(--high)', bg: 'rgba(240, 138, 93, 0.14)' }
    };
    return map[type] || map.summary;
  }

  getStatusConfig(status: ReportStatus) {
    const map: any = {
      ready: { label: 'Ready', color: 'var(--low)', bg: 'rgba(16, 217, 160, 0.14)', icon: 'pi-check-circle' },
      generating: { label: 'Generating...', color: 'var(--medium)', bg: 'rgba(255, 176, 32, 0.14)', icon: 'pi-spin pi-spinner' },
      pending: { label: 'Pending', color: 'var(--text-secondary)', bg: 'rgba(122, 156, 201, 0.15)', icon: 'pi-clock' },
      failed: { label: 'Failed', color: 'var(--critical)', bg: 'rgba(255, 77, 77, 0.14)', icon: 'pi-exclamation-circle' }
    };
    return map[status] || map.pending;
  }

  ngOnInit() {
    setTimeout(() => {
      this.isLoading.set(false);
    }, 800);
  }

  onDownload(reportId: string) {
    this.reportService.downloadReport(reportId).subscribe({
      next: (res) => {
        const link = document.createElement('a');
        link.href = res.download_url;
        link.target = '_blank';
        link.download = `Report_${reportId}.pdf`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      },
      error: (err) => console.error('Download failed', err)
    });
  }
}
