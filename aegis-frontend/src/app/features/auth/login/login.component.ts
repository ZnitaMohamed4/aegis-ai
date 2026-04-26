import { Component, inject, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../../core/services/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './login.html',
  styleUrl: './login.css'
})
export class LoginComponent implements OnInit, OnDestroy {
  private authService = inject(AuthService);
  private router = inject(Router);

  username = '';
  password = '';
  errorMessage = '';
  isLoading = false;

  private authSub: any;

  ngOnInit() {
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

  onSubmit() {
    if (!this.username || !this.password) return;
    
    this.isLoading = true;
    this.errorMessage = '';
    
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
