import { Component, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DrawerModule } from 'primeng/drawer';
import { ToastModule } from 'primeng/toast';
import { MessageService } from 'primeng/api';
import { RouterLink } from '@angular/router';
import { getRiskHex } from '@shared/utils/severity.utils';
import { AccountStatus, ParentUser, MOCK_USERS } from './users.data';

@Component({
  selector: 'app-users',
  standalone: true,
  imports: [CommonModule, FormsModule, DrawerModule, ToastModule, RouterLink],
  providers: [MessageService],
  templateUrl: './users.html',
  styleUrl: './users.css'
})
export class UsersComponent {

  constructor(private readonly messageService: MessageService) {}

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

  users = signal<ParentUser[]>(MOCK_USERS);

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
    const missingStep2 = !form.child_identifier.trim() || !form.child_whatsapp.trim();
    if (missingStep2) {
      this.messageService.add({
        severity: 'warn',
        summary: 'Missing Child Info',
        detail: 'Please fill child identifier and WhatsApp number before creating the account.'
      });
      return;
    }

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

    const now = new Date();
    const joinedAt = now.toLocaleDateString('en', { month: 'short', day: 'numeric', year: 'numeric' });

    const createdParent: ParentUser = {
      id: crypto.randomUUID(),
      full_name: form.full_name.trim(),
      email: form.email.trim(),
      phone: form.phone.trim(),
      status: 'active',
      monitoring_active: true,
      alert_threshold: form.alert_threshold,
      sms_notifications: form.sms_notifications,
      email_notifications: form.email_notifications,
      linked_child: {
        identifier: form.child_identifier.trim(),
        whatsapp_number: form.child_whatsapp.trim(),
        risk_level: 'low',
        whatsapp_connected: false
      },
      joined_at: joinedAt,
      last_login: 'Never'
    };

    this.users.update(list => [createdParent, ...list]);

    this.newUser.set({ ...this.emptyNewUser });
    this.createStep.set(1);
    this.drawerVisible.set(false);
    this.drawerMode.set(null);

    this.messageService.add({
      severity: 'success',
      summary: 'Parent Created',
      detail: `${createdParent.full_name} has been added successfully.`
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
}
