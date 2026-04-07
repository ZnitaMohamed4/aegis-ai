import { Component, inject, signal } from '@angular/core';
import { User } from '@core/models';
import { RouterOutlet } from "@angular/router";
import { ThemeService } from '@core/services/theme.service';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet],
  templateUrl: './app.html',
  styleUrl: './app.css'
})
export class App {
  private readonly theme = inject(ThemeService);
  protected readonly title = signal('aegis-ai');
}
