import { Component, signal, computed, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DrawerModule } from 'primeng/drawer';
import { ToastModule } from 'primeng/toast';
import { MessageService } from 'primeng/api';
import { RouterLink } from '@angular/router';
import { getRiskHex } from '@shared/utils/severity.utils';
import { AccountStatus, ParentUser, MOCK_USERS } from './users.data';
import { ApiService } from '@core/services/api.service';

@Component({
  selector: 'app-users',
  standalone: true,
  imports: [CommonModule, FormsModule, DrawerModule, ToastModule, RouterLink],
  providers: [MessageService],
  templateUrl: './users.html',
  styleUrl: './users.css'
})
export class UsersComponent implements OnInit {

  constructor(private readonly messageService: MessageService) {}
  private apiService = inject(ApiService);

  searchQuery = signal('');
  drawerVisible = signal(false);
  drawerMode = signal<'view' | 'create' | null>(null);
  selectedUser = signal<ParentUser | null>(null);
  createStep = signal<1 | 2>(1);

  newUser = signal({
    full_name: '',
    email: '',
    phone: '',
    child_identifier: '',
    child_whatsapp: '',
    alert_threshold: 0.75,
    sms_notifications: true,
    email_notifications: true
  });

  private readonly emptyNewUser = {
    full_name: '',
    email: '',
    phone: '',
    child_identifier: '',
    child_whatsapp: '',
    alert_threshold: 0.75,
    sms_notifications: true,
    email_notifications: true
  };

  users = signal<ParentUser[]>([]);

  ngOnInit() {
    this.apiService.getAdminUsers().subscribe({
      next: (data) => {
        this.users.set(data);
      },
      error: (err) => {
        console.error('Failed to load admin users from backend, falling back to mock data.', err);
        this.users.set(MOCK_USERS);
        this.messageService.add({
          severity: 'warn',
          summary: 'Offline Mode',
          detail: 'Showing mock users because backend connection failed.'
        });
      }
    });
  }

  filteredUsers = computed(() =>
    this.users().filter(u =>
      u.full_name.toLowerCase().includes(this.searchQuery().toLowerCase()) ||
      u.email.toLowerCase().includes(this.searchQuery().toLowerCase())
    )
  );

  linkedCount = computed(() => this.users().filter(u => u.linked_child !== null).length);
  activeCount = computed(() => this.users().filter(u => u.status === 'active').length);
  unlinkedCount = computed(() => this.users().filter(u => u.linked_child === null).length);

  getRiskHex = getRiskHex;

  openView(user: ParentUser) {
    this.selectedUser.set(user);
    this.drawerMode.set('view');
    this.drawerVisible.set(true);
  }

  openCreate() {
    this.createStep.set(1);
    this.selectedUser.set(null);
    this.newUser.set({ ...this.emptyNewUser });
    this.drawerMode.set('create');
    this.drawerVisible.set(true);
  }

  closeDrawer() {
    this.drawerVisible.set(false);
    this.drawerMode.set(null);
  }

  updateNewUserField(field: keyof ReturnType<UsersComponent['newUser']>, value: string | number | boolean) {
    this.newUser.update(u => ({ ...u, [field]: value }));
  }

  createAccount() {
    const form = this.newUser();
    
    // Front-end validation
    const requiredMissing = !form.full_name.trim() || !form.email.trim() || !form.phone.trim();
    if (requiredMissing) {
      this.messageService.add({
        severity: 'warn',
        summary: 'Missing Parent Info',
        detail: 'Please complete name, email, and phone before continuing.'
      });
      return;
    }

    const emailOk = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim());
    if (!emailOk) {
      this.messageService.add({
        severity: 'warn',
        summary: 'Invalid Email',
        detail: 'Please enter a valid email address.'
      });
      return;
    }
    
    // Check local duplicate emails just as a quick front-end safety net
    const duplicateEmail = this.users().some(
      u => u.email.toLowerCase() === form.email.trim().toLowerCase()
    );

    if (duplicateEmail) {
      this.messageService.add({
        severity: 'error',
        summary: 'Email Already Exists',
        detail: 'A parent account with this email already exists.'
      });
      return;
    }

    // Call the backend API instead of mocking it!
    this.apiService.createAdminUser(form).subscribe({
      next: () => {
        this.messageService.add({
          severity: 'success',
          summary: 'Parent Created',
          detail: `${form.full_name} has been added successfully.`
        });
        
        // Refresh the user list from the database
        this.ngOnInit();
        
        // Reset the drawer
        this.newUser.set({ ...this.emptyNewUser });
        this.createStep.set(1);
        this.drawerVisible.set(false);
        this.drawerMode.set(null);
      },
      error: (err) => {
        this.messageService.add({
          severity: 'error',
          summary: 'Creation Failed',
          detail: err.error?.error || 'Could not create the parent account.'
        });
      }
    });
  }

  proceedToChildStep() {
    const form = this.newUser();
    const requiredMissing = !form.full_name.trim() || !form.email.trim() || !form.phone.trim();
    if (requiredMissing) {
      this.messageService.add({
        severity: 'warn',
        summary: 'Missing Parent Info',
        detail: 'Please complete name, email, and phone before continuing.'
      });
      return;
    }

    const emailOk = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim());
    if (!emailOk) {
      this.messageService.add({
        severity: 'warn',
        summary: 'Invalid Email',
        detail: 'Please enter a valid email address.'
      });
      return;
    }

    this.createStep.set(2);
  }

  toggleMonitoring(user: ParentUser) {
    this.users.update(list =>
      list.map(u => u.id === user.id
        ? { ...u, monitoring_active: !u.monitoring_active }
        : u
      )
    );
    if (this.selectedUser()?.id === user.id) {
      this.selectedUser.update(u => u ? { ...u, monitoring_active: !u.monitoring_active } : u);
    }
  }

  toggleStatus(user: ParentUser) {
    this.users.update(list =>
      list.map(u => u.id === user.id
        ? { ...u, status: u.status === 'active' ? 'inactive' : 'active' }
        : u
      )
    );
  }

  getStatusClass(status: AccountStatus): string {
    const map: Record<string, string> = {
      active: 'status-active',
      inactive: 'status-inactive',
      suspended: 'status-suspended'
    };
    return map[status];
  }

  getInitials(name: string): string {
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
  }

  deleteParent(user: ParentUser) {
    if (confirm(`Are you sure you want to permanently delete ${user.full_name}'s account and ALL associated children/data? This action cannot be undone.`)) {
      this.apiService.deleteAdminUser(user.id).subscribe({
        next: () => {
          this.messageService.add({
            severity: 'success',
            summary: 'Account Deleted',
            detail: `${user.full_name}'s account has been permanently removed.`
          });
          this.closeDrawer();
          this.ngOnInit(); // Refresh list
        },
        error: (err) => {
          this.messageService.add({
            severity: 'error',
            summary: 'Deletion Failed',
            detail: err.error?.error || 'Could not delete the parent account.'
          });
        }
      });
    }
  }
}
