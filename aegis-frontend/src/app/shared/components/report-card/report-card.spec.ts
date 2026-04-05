import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ReportCard } from './report-card';

describe('ReportCard', () => {
  let component: ReportCard;
  let fixture: ComponentFixture<ReportCard>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ReportCard],
    }).compileComponents();

    fixture = TestBed.createComponent(ReportCard);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
