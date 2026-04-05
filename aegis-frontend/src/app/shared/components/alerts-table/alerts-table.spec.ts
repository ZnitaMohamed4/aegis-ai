import { ComponentFixture, TestBed } from '@angular/core/testing';

import { AlertsTable } from './alerts-table';

describe('AlertsTable', () => {
  let component: AlertsTable;
  let fixture: ComponentFixture<AlertsTable>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AlertsTable],
    }).compileComponents();

    fixture = TestBed.createComponent(AlertsTable);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
