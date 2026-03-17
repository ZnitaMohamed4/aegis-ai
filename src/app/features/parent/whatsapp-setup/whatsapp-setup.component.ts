import { Component, signal, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-whatsapp-setup',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './whatsapp-setup.html',
  styleUrls: ['./whatsapp-setup.css']
})
export class WhatsappSetupComponent implements OnDestroy {
  connectionStatus = signal<'idle' | 'qr_displayed' | 'connected'>('idle');
  
  // Timer for QR expiry
  qrTimeRemaining = signal<number>(45);
  qrInterval: any;

  // Mock data for success state
  connectedNumber = '+212 612 345 678';
  connectionDate = new Date().toLocaleDateString(undefined, { 
    year: 'numeric', month: 'short', day: 'numeric', 
    hour: '2-digit', minute: '2-digit' 
  });

  showDisconnectDialog = signal<boolean>(false);

  generateQr() {
    this.connectionStatus.set('qr_displayed');
    this.startQrTimer();
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
  }

  refreshQr() {
    this.startQrTimer();
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
  }
}
