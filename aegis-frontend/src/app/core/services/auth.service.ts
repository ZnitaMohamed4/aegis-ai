import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, tap } from 'rxjs';
import { environment } from '../../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private apiUrl = `${environment.apiBaseUrl}/auth`;
  private currentUserSubject = new BehaviorSubject<any>(null);
  public currentUser$ = this.currentUserSubject.asObservable();

  constructor(private http: HttpClient) {
    this.loadUserFromStorage();
  }

  // 1. Login - gets tokens
  login(credentials: any) {
    return this.http.post(`${this.apiUrl}/login/`, credentials).pipe(
      tap((response: any) => {
        localStorage.setItem('access_token', response.access);
        localStorage.setItem('refresh_token', response.refresh);
        this.fetchCurrentUser(); // Get the user details
      })
    );
  }

  // 2. Register
  register(userData: any) {
    return this.http.post(`${this.apiUrl}/register/`, userData);
  }

  // 3. Fetch "Me"
  fetchCurrentUser() {
    this.http.get(`${this.apiUrl}/me/`).subscribe({
      next: (user: any) => {
        this.currentUserSubject.next(user);
        localStorage.setItem('aegis_role', user.role); // Save role for synchronous guards
      },
      error: (err) => {
        console.error("Auth check failed", err);
        // Only logout if it's a 401/403 (unauthorized)
        if (err.status === 401 || err.status === 403) {
          this.logout();
        }
      }
    });
  }

  // Load user on page refresh
  private loadUserFromStorage() {
    const token = this.getToken();
    if (token) {
      this.fetchCurrentUser();
    }
  }

  getToken() {
    return localStorage.getItem('access_token');
  }

  isLoggedIn() {
    return !!this.getToken();
  }

  getRole() {
    // Return the role from the subject if loaded, otherwise fallback to storage
    const user = this.currentUserSubject.value;
    if (user && user.role) return user.role;
    return localStorage.getItem('aegis_role');
  }

  logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('aegis_role');
    this.currentUserSubject.next(null);
    // Use relative path for internal routing
    window.location.href = '/login';
  }
}



