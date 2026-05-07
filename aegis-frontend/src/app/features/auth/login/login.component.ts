import { Component, inject, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../../core/services/auth.service';
import { MessageService } from 'primeng/api';
import { ToastModule } from 'primeng/toast';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule, ToastModule],
  providers: [MessageService],
  templateUrl: './login.html',
  styleUrl: './login.css'
})
export class LoginComponent implements OnInit, OnDestroy {
  private authService = inject(AuthService);
  private router = inject(Router);
  private messageService = inject(MessageService);

  username = '';
  password = '';
  rememberMe = false;
  errorMessage = '';
  isLoading = false;

  private authSub: any;

  ngOnInit() {
    const savedUsername = localStorage.getItem('aegis_remembered_username');
    if (savedUsername) {
      this.username = savedUsername;
      this.rememberMe = true;
    }

    // If we're already logged in, redirect immediately
    this.authSub = this.authService.currentUser$.subscribe(user => {
      if (user) {
        if (user.role === 'admin') {
          this.router.navigate(['/admin/dashboard']);
        } else {
          this.router.navigate(['/parent/dashboard']);
        }
      }
    });
  }

  ngOnDestroy() {
    if (this.authSub) {
      this.authSub.unsubscribe();
    }
  }

  forgotPassword(event: Event) {
    event.preventDefault();
    this.messageService.add({ severity: 'info', summary: 'Reset Link Sent', detail: 'If your email is registered, you will receive a password reset link.', life: 3000 });
  }

  onSubmit() {
    if (!this.username || !this.password) return;
    
    this.isLoading = true;
    this.errorMessage = '';
    
    if (this.rememberMe) {
      localStorage.setItem('aegis_remembered_username', this.username);
    } else {
      localStorage.removeItem('aegis_remembered_username');
    }
    
    this.authService.login({ username: this.username, password: this.password }).subscribe({
      next: () => {
        // The subscription in ngOnInit will handle the redirect once the user data loads!
      },
      error: (err) => {
        this.isLoading = false;
        this.errorMessage = 'Invalid username or password. Please try again.';
      }
    });
  }
}
