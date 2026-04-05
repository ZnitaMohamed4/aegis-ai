import { Component, input } from '@angular/core';
import { getRiskHex } from '@shared/utils/severity.utils';

@Component({
  selector: 'app-severity-badge',
  standalone: true,
  template: `
    <span class="text-xs font-bold capitalize px-2.5 py-1 rounded-full"
          [style.color]="getColor()"
          [style.background]="getColor() + '22'">
      {{ level() }}
    </span>
  `
})
export class SeverityBadgeComponent {
  level = input.required<string>();
  getColor() { return getRiskHex(this.level()); }
}
