import { Component, OnInit, signal, computed, effect } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ChartModule } from 'primeng/chart';
import { SelectButtonModule } from 'primeng/selectbutton';
import { TableModule } from 'primeng/table';

import { PageHeaderComponent, StatCardComponent, SeverityBadgeComponent } from '@shared/index';
import { getRiskHex, getThreatHex } from '@shared/utils/severity.utils';

import { ANALYTICS_DATA } from './analytics.data';

type TimeRange = '7D' | '30D';

@Component({
  selector: 'app-analytics',
  standalone: true,
  imports: [
    CommonModule, 
    FormsModule, 
    ChartModule, 
    SelectButtonModule,
    TableModule,
    PageHeaderComponent, 
    StatCardComponent, 
    SeverityBadgeComponent
  ],
  templateUrl: './analytics.html',
  styleUrl: './analytics.css',
})
export class AnalyticsComponent implements OnInit {
  // Time Range
  timeRangeOptions = [
    { label: 'Last 7 Days', value: '7D' },
    { label: 'Last 30 Days', value: '30D' }
  ];
  selectedRange = signal<TimeRange>('30D');

  // Charts data
  riskOptions: any;
  riskData: any;
  
  decisionsOptions: any;
  decisionsData: any;

  categoriesOptions: any;
  categoriesData: any;

  latencyOptions: any;
  latencyData: any;

  langOptions: any;
  langData: any;

  notificationOptions: any;
  notificationData: any;

  // NEW CHARTS
  confDistOptions: any;
  confDistData: any;

  agent3Options: any;
  agent3Data: any;

  falsePosOptions: any;
  falsePosData: any;

  reviewPieOptions: any;
  reviewPieData: any;

  // Heatmap
  days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  hours = Array.from({ length: 24 }, (_, i) => i);
  heatmapData = signal<{ val: number, color: string }[][]>([]);
  heatmapMax = 0;

  reviewAvgTime = signal(ANALYTICS_DATA.reviewQueue.avgResolutionTime);

  // Tables
  topHarassers = signal(ANALYTICS_DATA.topHarassers);
  perChildRisk = signal(ANALYTICS_DATA.perChildRisk);

  // Stats
  getStatColor = getThreatHex;

  constructor() {
    effect(() => {
      this.updateCharts(this.selectedRange());
    });
  }

  ngOnInit() {
    this.initChartOptions();
    this.updateCharts(this.selectedRange());
  }

  initChartOptions() {
    const textColor = '#94A3B8';
    const textColorSecondary = '#64748B';
    const surfaceBorder = '#1E3A5F33';

    const baseOptions = {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: textColor, font: { family: 'Inter', size: 12 } } },
        tooltip: {
          backgroundColor: '#0F172A', titleColor: '#E2E8F0', bodyColor: textColor,
          borderColor: '#1E3A5F', borderWidth: 1
        }
      },
      scales: {
        x: { ticks: { color: textColorSecondary, font: { size: 11 } }, grid: { color: surfaceBorder } },
        y: { ticks: { color: textColorSecondary, font: { size: 11 } }, grid: { color: surfaceBorder } }
      }
    };

    this.riskOptions = { ...baseOptions };
    
    this.decisionsOptions = {
      ...baseOptions,
      plugins: { ...baseOptions.plugins, tooltip: { ...baseOptions.plugins.tooltip, mode: 'index' } },
      scales: {
        x: { ...baseOptions.scales.x, stacked: true },
        y: { ...baseOptions.scales.y, stacked: true }
      }
    };

    this.categoriesOptions = { ...this.decisionsOptions };
    this.latencyOptions = { ...baseOptions };

    this.langOptions = {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'right', labels: { color: textColor, usePointStyle: true } }
      }
    };
    this.notificationOptions = this.langOptions;
    
    // Confidence Distribution Histogram
    this.confDistOptions = {
      ...baseOptions,
      scales: {
        x: { ...baseOptions.scales.x, title: { display: true, text: 'Confidence Score Range', color: textColorSecondary } },
        y: { ...baseOptions.scales.y, title: { display: true, text: 'Messages Count', color: textColorSecondary } }
      }
    };

    // Agent 3 Activation & False Positive Line Charts
    this.agent3Options = {
      ...baseOptions,
      scales: {
        ...baseOptions.scales,
        y: { ...baseOptions.scales.y, title: { display: true, text: 'Trigger Rate (%)', color: textColorSecondary } }
      }
    };

    this.falsePosOptions = {
      ...baseOptions,
      scales: {
        ...baseOptions.scales,
        y: { ...baseOptions.scales.y, title: { display: true, text: 'False Positive Rate (%)', color: textColorSecondary } }
      }
    };

    // Review Queue Decisions
    this.reviewPieOptions = this.langOptions;
  }

  updateCharts(range: TimeRange) {
    const days = range === '7D' ? 7 : 30;
    const sliceEnd = 30;
    const sliceStart = 30 - days;

    const labels = ANALYTICS_DATA.labels.slice(sliceStart, sliceEnd);

    // 1. Risk Score Evolution (Line)
    this.riskData = {
      labels,
      datasets: [
        {
          label: 'Average Risk Score',
          data: ANALYTICS_DATA.riskScores.slice(sliceStart, sliceEnd),
          borderColor: '#06B6D4',
          backgroundColor: '#06B6D41A',
          borderWidth: 2,
          fill: true,
          tension: 0.4
        }
      ]
    };

    // 2. Decisions Trend (Stacked Bar)
    this.decisionsData = {
      labels,
      datasets: [
        { label: 'Blocked', data: ANALYTICS_DATA.decisions.blocked.slice(sliceStart, sliceEnd), backgroundColor: '#EF4444' },
        { label: 'Warned', data: ANALYTICS_DATA.decisions.warned.slice(sliceStart, sliceEnd), backgroundColor: '#EAB308' },
        { label: 'Allowed', data: ANALYTICS_DATA.decisions.allowed.slice(sliceStart, sliceEnd), backgroundColor: '#22C55E' }
      ]
    };

    // 3. Category Breakdown (Stacked Bar)
    this.categoriesData = {
      labels,
      datasets: [
        { label: 'Verbal', data: ANALYTICS_DATA.categories.verbal.slice(sliceStart, sliceEnd), backgroundColor: '#F97316' },
        { label: 'Threat', data: ANALYTICS_DATA.categories.threat.slice(sliceStart, sliceEnd), backgroundColor: '#EF4444' },
        { label: 'Sexual', data: ANALYTICS_DATA.categories.sexual.slice(sliceStart, sliceEnd), backgroundColor: '#A855F7' },
        { label: 'Discrim.', data: ANALYTICS_DATA.categories.discrimination.slice(sliceStart, sliceEnd), backgroundColor: '#EAB308' }
      ]
    };

    // 4. Pipeline Latency (Line)
    this.latencyData = {
      labels,
      datasets: [
        {
          label: 'Latency (ms)',
          data: ANALYTICS_DATA.latency.slice(sliceStart, sliceEnd),
          borderColor: '#8B5CF6',
          backgroundColor: '#8B5CF61A',
          borderWidth: 2,
          fill: true,
          tension: 0.4
        }
      ]
    };

    // 5. Language Stats (Pie/Doughnut)
    this.langData = {
      labels: ['French (FR)', 'Arabic (AR)', 'English (EN)'],
      datasets: [{
        data: ANALYTICS_DATA.languageDistribution,
        backgroundColor: ['#06B6D4', '#EAB308', '#22C55E'],
        hoverBackgroundColor: ['#0891B2', '#CA8A04', '#16A34A'],
        borderWidth: 0
      }]
    };

    // 6. Notifications Stats (Doughnut)
    this.notificationData = {
      labels: ['SMS', 'Email', 'Push', 'Appel'],
      datasets: [{
        data: ANALYTICS_DATA.notificationStats,
        backgroundColor: ['#F97316', '#38BDF8', '#8B5CF6', '#EF4444'],
        hoverBackgroundColor: ['#EA580C', '#0284C7', '#7C3AED', '#DC2626'],
        borderWidth: 0
      }]
    };

    // 7. Confidence Score Distribution (Bar - Histogram)
    this.confDistData = {
      labels: ANALYTICS_DATA.confidenceDistribution.labels,
      datasets: [{
        label: 'Messages Count',
        data: ANALYTICS_DATA.confidenceDistribution.data,
        backgroundColor: ['#22C55E', '#8B5CF6', '#EAB308', '#F97316', '#EF4444'], // Safe -> Grey Zone -> Critical
        borderWidth: 0,
        barPercentage: 1.0,  // removes gap between bars to look like a histogram
        categoryPercentage: 1.0
      }]
    };

    // 8. Agent 3 Activation Rate (Line)
    this.agent3Data = {
      labels,
      datasets: [{
        label: 'Agent 3 Activation (%)',
        data: ANALYTICS_DATA.agent3Activation.slice(sliceStart, sliceEnd),
        borderColor: '#A855F7',
        backgroundColor: '#A855F71A',
        borderWidth: 2,
        fill: true,
        tension: 0.4
      }]
    };

    // 9. False Positives Trend (Line)
    this.falsePosData = {
      labels,
      datasets: [{
        label: 'False Positive Rate (%)',
        data: ANALYTICS_DATA.falsePositives.slice(sliceStart, sliceEnd),
        borderColor: '#EAB308',
        backgroundColor: '#EAB3081A',
        borderWidth: 2,
        borderDash: [5, 5],
        fill: true,
        tension: 0.4
      }]
    };

    // 10. Review Queue Decisions
    this.reviewPieData = {
      labels: ['Confirmed Block', 'Reversed to Allow'],
      datasets: [{
        data: ANALYTICS_DATA.reviewQueue.decisions,
        backgroundColor: ['#EF4444', '#22C55E'],
        hoverBackgroundColor: ['#DC2626', '#16A34A'],
        borderWidth: 0
      }]
    };

    // 11. Heatmap Data Generation
    const rawHeatmap = ANALYTICS_DATA.peakActivity;
    let max = 0;
    for (const day of rawHeatmap) {
      for (const val of day) {
        if (val > max) max = val;
      }
    }
    this.heatmapMax = max;

    const heatmapStyles = rawHeatmap.map(dayArr => {
      return dayArr.map(val => {
        const intensity = (val / max);
        // We will blend from surface color to a deep red/orange for "heat"
        // Let's use CSS directly or mapped colors. Actually we can return an opacity to apply to a #EF4444 background.
        // A minimal intensity so 0 is still faintly visible, e.g., max 0.8 opacity.
        const opacity = Math.max(0.05, intensity * 0.9);
        return { val, color: `rgba(239, 68, 68, ${opacity})` };
      });
    });
    this.heatmapData.set(heatmapStyles);
  }
}
