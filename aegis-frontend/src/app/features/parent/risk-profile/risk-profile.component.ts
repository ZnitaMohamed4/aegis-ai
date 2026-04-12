import { Component, OnInit, signal, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ChartModule } from 'primeng/chart';
import { getRiskHex } from '@shared/utils/severity.utils';
import { ApiService } from '@core/services/api.service';

@Component({
  selector: 'app-risk-profile',
  standalone: true,
  imports: [CommonModule, ChartModule],
  templateUrl: './risk-profile.html',
  styleUrl: './risk-profile.css'
})
export class RiskProfileComponent implements OnInit {
  childName = signal('Loading...');
  childNumber = signal('Loading...');
  currentRiskScore = signal(0);
  currentRiskLevel = signal('low');
  
  threatActors = signal<any[]>([]);

  riskChartData: any;
  riskChartOptions: any;

  getRiskHex = getRiskHex;
  private apiService = inject(ApiService);

  ngOnInit() {
    this.initChartOptions();
    this.apiService.getParentRiskProfile().subscribe({
      next: (data: any) => {
        this.childName.set(data.child?.name || 'Your Child');
        this.childNumber.set(data.child?.number || 'Unknown');
        this.currentRiskLevel.set(data.risk_level || 'low');
        this.currentRiskScore.set(data.risk_score || 0.1);
        
        let actors = data.threat_actors || [];
        // Extract plain number from JID for display
        actors = actors.map((a: any) => ({
          ...a,
          name: a.name.split('@')[0],
          number: a.number.split('@')[0]
        }));
        
        this.threatActors.set(actors);

        if (data.risk_trend) {
          const accentColor = getComputedStyle(document.body).getPropertyValue('--accent') || '#3b82f6';
          const surfaceColor = getComputedStyle(document.body).getPropertyValue('--bg-surface') || '#1e293b';

          this.riskChartData = {
            labels: data.risk_trend.labels,
            datasets: [
              {
                label: 'Risk Score',
                data: data.risk_trend.data,
                fill: true,
                borderColor: accentColor,
                backgroundColor: `${accentColor}22`,
                tension: 0.4,
                borderWidth: 3,
                pointBackgroundColor: surfaceColor,
                pointBorderColor: accentColor,
                pointBorderWidth: 2,
                pointRadius: 4,
              }
            ]
          };
        }
      },
      error: (err) => console.error('[AEGIS] Failed to load risk profile', err)
    });
  }

  initChartOptions() {
    const textColor = getComputedStyle(document.body).getPropertyValue('--text-primary') || '#f8fafc';
    const textColorSecondary = getComputedStyle(document.body).getPropertyValue('--text-muted') || '#94a3b8';
    const surfaceBorder = getComputedStyle(document.body).getPropertyValue('--border') || '#334155';

    this.riskChartOptions = {
        maintainAspectRatio: false,
        plugins: {
            legend: {
                display: false
            },
            tooltip: {
                mode: 'index',
                intersect: false,
                callbacks: {
                    label: function(context: any) {
                        let label = context.dataset.label || '';
                        if (label) {
                            label += ': ';
                        }
                        if (context.parsed.y !== null) {
                            label += Math.round(context.parsed.y * 100) + '%';
                        }
                        return label;
                    }
                }
            }
        },
        scales: {
            x: {
                ticks: {
                    color: textColorSecondary
                },
                grid: {
                    color: surfaceBorder,
                    drawBorder: false
                }
            },
            y: {
                ticks: {
                    color: textColorSecondary
                },
                grid: {
                    color: surfaceBorder,
                    drawBorder: false
                },
                min: 0,
                max: 1.0
            }
        }
    };
  }
}

