import { Component, signal, computed, inject, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DrawerModule } from 'primeng/drawer';
import { ReportCardComponent } from '@shared/index';
import { ReportStatus, ReportType, Report, DeliveryChannel } from '@core/models';
import { ReportService } from '@core/services/report.service';
import { AuthService } from '@core/services/auth.service';
import { ApiService } from '@core/services/api.service';
import { AlertService } from '@core/services/alert.service';
import { Subscription } from 'rxjs';

@Component({
  selector: 'app-reports',
  standalone: true,
  imports: [CommonModule, FormsModule, DrawerModule, ReportCardComponent],
  templateUrl: './reports.html',
  styleUrl: './reports.css'
})
export class ParentReportsComponent implements OnInit, OnDestroy {
  private reportService = inject(ReportService);
  private authService = inject(AuthService);
  private apiService = inject(ApiService);
  private alertService = inject(AlertService);
  private wsSub?: Subscription;

  requestDrawerVisible = signal(false);
  isGenerating = signal(false);

  // Dynamic user data
  profileLoading = signal(true);
  parentName = signal('Loading...');
  parentEmail = signal('');
  parentPhone = signal('');

  requestForm = signal({
    child_id: '', // Will populate dynamically if needed
    period_start: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    period_end: new Date().toISOString().split('T')[0],
    report_type: 'summary' as ReportType,
    delivery_channel: 'dashboard' as DeliveryChannel
  });

  filterStatus = signal<string>('all');
  filterType = signal<string>('all');

  reports = signal<Report[]>([]);

  filteredReports = computed(() =>
    this.reports().filter(r => {
      const matchStatus = this.filterStatus() === 'all' || r.status === this.filterStatus();
      const matchType = this.filterType() === 'all' || r.report_type === this.filterType();
      return matchStatus && matchType;
    })
  );

  ngOnInit() {
    this.authService.fetchCurrentUser();
    this.loadReports();
    this.subscribeToWS();
    this.authService.currentUser$.subscribe(user => {
      if (user) {
        this.parentName.set(`${user.first_name || ''} ${user.last_name || ''}`.trim() || user.username);
        this.parentEmail.set(user.email || '');
        this.parentPhone.set(user.phone_number || '');
        this.profileLoading.set(false);
      }
    });
    
    // Auto-fetch child ID
    this.apiService.getParentDashboardStats().subscribe({
      next: (data) => {
        if (data.child) {
          this.requestForm.update(f => ({ ...f, child_id: data.child!.id }));
        }
      }
    });
  }

  ngOnDestroy() {
    this.wsSub?.unsubscribe();
  }

  /** Listen for REPORT_READY via WebSocket instead of polling */
  subscribeToWS() {
    this.wsSub = this.alertService.alerts$.subscribe((event: any) => {
      if (event.event === 'REPORT_READY' || event.type === 'REPORT_READY') {
        console.log('[AEGIS] Report ready via WebSocket, refreshing list.');
        this.loadReports();
      }
    });
  }

  loadReports() {
    this.reportService.getParentReports().subscribe({
      next: (data) => this.reports.set(data),
      error: (err) => console.error('Failed to load reports', err)
    });
  }

  openRequest() {
    this.authService.fetchCurrentUser();
    this.requestDrawerVisible.set(true);
  }

  submitRequest() {
    if (this.isGenerating()) return;
    this.isGenerating.set(true);
    
    // Instantly close the drawer for maximum fluidity
    this.requestDrawerVisible.set(false);
    
    const payload = this.requestForm();
    this.reportService.generateReport(payload).subscribe({
      next: (res) => {
        this.isGenerating.set(false);
        this.loadReports(); // Refresh to show the new report
      },
      error: (err) => {
        this.isGenerating.set(false);
        console.error('Failed to trigger report', err);
      }
    });
  }

  setReportType(type: string) {
    this.requestForm.update(f => ({ ...f, report_type: type as ReportType }));
  }

  setDeliveryChannel(channel: string) {
    this.requestForm.update(f => ({ ...f, delivery_channel: channel as DeliveryChannel }));
  }
}
