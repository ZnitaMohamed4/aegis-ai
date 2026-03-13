import { Component, input } from '@angular/core';

@Component({
  selector: 'app-stat-card',
  standalone: true,
  templateUrl: './stat-card.html',
  styleUrl: './stat-card.css'
})
export class StatCardComponent {
  label = input.required<string>();
  value = input.required<string | number>();
  sub = input<string>();
  trend = input<string>();
  valueColor = input<string>();
  borderColor = input<string>();
}
