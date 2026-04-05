import { Component, input } from '@angular/core';

@Component({
  selector: 'app-page-header',
  standalone: true,
  template: `
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
      <div>
        <h1 class="text-xl sm:text-2xl font-bold text-[var(--text-primary)] mb-1">{{ title() }}</h1>
        @if (subtitle()) {
          <p class="text-sm text-[var(--text-muted)]">{{ subtitle() }}</p>
        }
      </div>
      <ng-content />
    </div>
  `
})
export class PageHeaderComponent {
  title = input.required<string>();
  subtitle = input<string>();
}
