import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';

@Injectable({ providedIn: 'root' })
export class WhatsappService {
  constructor(private http: HttpClient) {}

  getQRCode() {
    return this.http.get<any>('http://localhost:8000/api/v1/auth/qr-code/');
  }

  checkConnectionStatus() {
    return this.http.get<any>('http://localhost:8000/api/v1/auth/check-connection/');
  }
}
