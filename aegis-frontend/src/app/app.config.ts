import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideAnimations } from '@angular/platform-browser/animations';
import { providePrimeNG } from 'primeng/config';
import { MessageService, ConfirmationService } from 'primeng/api';
import Aura from '@primeuix/themes/aura';
import { routes } from './app.routes';
import { jwtInterceptor } from '@core/interceptors/jwt.interceptor';

export const appConfig: ApplicationConfig = {
  providers: [
      provideBrowserGlobalErrorListeners(),
      provideRouter(routes),
      provideHttpClient(withInterceptors([jwtInterceptor])),
      provideAnimations(),
      MessageService,
      ConfirmationService,
      providePrimeNG({
        theme: {
          preset: Aura,
          options: {
            darkModeSelector: '.dark',
            cssLayer: {
              name: 'primeng',
              order: 'tailwind-base, primeng, tailwind-utilities'
            }
          }
        }
      })
    ]
};