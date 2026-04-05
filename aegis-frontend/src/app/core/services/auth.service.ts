import { Injectable, signal } from '@angular/core';
import { Router } from '@angular/router';

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  role = signal<'admin' | 'parent' | null>(null);

  constructor(private router: Router) {
    const savedRole = localStorage.getItem('aegis_role');
    if (savedRole === 'admin' || savedRole === 'parent') {
      this.role.set(savedRole);
    }
  }

  login(selectedRole: 'admin' | 'parent') {
    this.role.set(selectedRole);
    localStorage.setItem('aegis_role', selectedRole);
  }

  logout() {
    this.role.set(null);
    localStorage.removeItem('aegis_role');
    this.router.navigate(['/login']);
  }

  getRole() {
    return this.role();
  }

  isLoggedIn() {
    return this.role() !== null;
  }
}
