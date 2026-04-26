import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Report, ReportType, DeliveryChannel } from '../models/report.model';
import { environment } from '../../../environments/environment';

export interface GenerateReportRequest {
  child_id?: string;
  period_start: string;
  period_end: string;
  report_type: ReportType;
  delivery_channel: DeliveryChannel;
}

export interface GenerateReportResponse {
  report_id: string;
  status: string;
}

export interface DownloadReportResponse {
  download_url: string;
}

@Injectable({
  providedIn: 'root'
})
export class ReportService {
  private http = inject(HttpClient);
  private readonly BASE_URL = environment.apiBaseUrl;
  
  // Parent endpoints
  getParentReports(childId?: string): Observable<Report[]> {
    const params: any = {};
    if (childId) params.child_id = childId;
    return this.http.get<Report[]>(`${this.BASE_URL}/parent/reports/`, { params });
  }

  // Admin endpoints
  getAdminReports(): Observable<Report[]> {
    return this.http.get<Report[]>(`${this.BASE_URL}/admin/reports/`);
  }

  // Generation
  generateReport(payload: GenerateReportRequest): Observable<GenerateReportResponse> {
    return this.http.post<GenerateReportResponse>(`${this.BASE_URL}/reports/generate/`, payload);
  }

  // Download
  downloadReport(reportId: string): Observable<DownloadReportResponse> {
    return this.http.get<DownloadReportResponse>(`${this.BASE_URL}/reports/${reportId}/download/`);
  }
}
