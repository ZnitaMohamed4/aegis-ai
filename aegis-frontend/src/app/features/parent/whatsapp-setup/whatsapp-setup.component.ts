import { Component, signal, OnDestroy, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { WhatsappService } from '../../../core/services/whatsapp.service';
import { AuthService } from '../../../core/services/auth.service';

@Component({
  selector: 'app-whatsapp-setup',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './whatsapp-setup.html',
  styleUrls: ['./whatsapp-setup.css']
})
export class WhatsappSetupComponent implements OnInit, OnDestroy {
  connectionStatus = signal<'loading_initial' | 'idle' | 'loading' | 'qr_displayed' | 'connected'>('loading_initial');
  qrCodeBase64 = signal<string>(''); // We will store the real QR image here!
  
  // Timer for QR expiry
  qrTimeRemaining = signal<number>(45);
  qrInterval: any;

  // Data for success state
  connectedNumber = 'Loading...';
  connectionDate = new Date().toLocaleDateString(undefined, { 
    year: 'numeric', month: 'short', day: 'numeric', 
    hour: '2-digit', minute: '2-digit' 
  });

  showDisconnectDialog = signal<boolean>(false);
  monitoringMode: string = 'child';
  private authService = inject(AuthService);

  constructor(private whatsappService: WhatsappService) {}

  ngOnInit() {
    this.authService.currentUser$.subscribe(user => {
      if (user && user.monitoring_mode) {
        this.monitoringMode = user.monitoring_mode;
      }
    });
    this.checkCurrentStatus();
  }

  checkCurrentStatus() {
    this.whatsappService.checkConnectionStatus().subscribe({
      next: (res) => {
        if (res.connected) {
          if (res.number) {
            this.connectedNumber = res.number;
          }
          this.connectionStatus.set('connected');
        } else {
          this.connectionStatus.set('idle');
        }
      },
      error: () => {
        this.connectionStatus.set('idle');
      }
    });
  }

  generateQr() {
    this.connectionStatus.set('loading');
    
    // Call the backend endpoint
    this.whatsappService.getQRCode().subscribe({
      next: (response) => {
        // Evolution API has slightly different names depending on version:
        const qrImage = response.base64 || response.qrcode || response.code || (response.data && response.data.qrcode);
        
        if (qrImage) {
          this.qrCodeBase64.set(qrImage);
          this.connectionStatus.set('qr_displayed');
          this.startQrTimer();
        } else {
          console.error("Failed to extract QR from response", response);
          this.connectionStatus.set('idle');
          alert("Could not load QR code. Try again.");
        }
      },
      error: (err) => {
        console.error("API error", err);
        this.connectionStatus.set('idle');
        alert("Server error linking WhatsApp.");
      }
    });
  }

  startQrTimer() {
    this.qrTimeRemaining.set(45);
    this.clearTimer();
    
    this.qrInterval = setInterval(() => {
      this.qrTimeRemaining.update(t => {
        if (t <= 1) {
          this.clearTimer();
          return 0;
        }
        return t - 1;
      });
    }, 1000);

    this.startPolling();
  }

  statusInterval: any;

  startPolling() {
    if (this.statusInterval) clearInterval(this.statusInterval);
    
    this.statusInterval = setInterval(() => {
      this.whatsappService.checkConnectionStatus().subscribe({
        next: (res) => {
          if (res.connected) {
            this.clearTimer();
            this.clearStatusPolling();
            if (res.number) {
              this.connectedNumber = res.number;
            }
            this.connectionStatus.set('connected');
          }
        }
      });
    }, 3000);
  }

  clearStatusPolling() {
    if (this.statusInterval) {
      clearInterval(this.statusInterval);
    }
  }

  refreshQr() {
    this.generateQr();
  }

  simulateScan() {
    this.clearTimer();
    this.connectionStatus.set('connected');
  }

  promptDisconnect() {
    this.showDisconnectDialog.set(true);
  }

  cancelDisconnect() {
    this.showDisconnectDialog.set(false);
  }

  confirmDisconnect() {
    this.showDisconnectDialog.set(false);
    this.connectionStatus.set('idle');
    this.qrTimeRemaining.set(45);
  }

  clearTimer() {
    if (this.qrInterval) {
      clearInterval(this.qrInterval);
    }
  }

  ngOnDestroy() {
    this.clearTimer();
    this.clearStatusPolling();
  }
}
