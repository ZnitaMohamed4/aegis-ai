import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AlertsTableComponent } from '@shared/components/alerts-table/alerts-table';
import { MOCK_ALERTS } from '@features/admin/alerts/alerts.data';
import { MockAlert } from '@core/models';

@Component({
  selector: 'app-alerts',
  standalone: true,
  imports: [CommonModule, AlertsTableComponent],
  templateUrl: './alerts.html',
  styleUrl: './alerts.css'
})
export class AlertsComponent {
  // Parent sees only their child's alerts (mocked as a subset)
  alerts = signal<MockAlert[]>(MOCK_ALERTS.slice(0, 3));

  onResolve(alert: MockAlert) {
    this.alerts.update(list =>
      list.map(a => a.id === alert.id ? { ...a, is_resolved: true } : a)
    );
  }
}
