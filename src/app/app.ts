import { Component, signal } from '@angular/core';
import { User } from '@core/models';

@Component({
  selector: 'app-root',
  imports: [],
  templateUrl: './app.html',
  styleUrl: './app.css'
})
export class App {
  protected readonly title = signal('aegis-ai-dashboard');
}
