import { ComponentFixture, TestBed } from '@angular/core/testing';

import { RiskProfile } from './risk-profile';

describe('RiskProfile', () => {
  let component: RiskProfile;
  let fixture: ComponentFixture<RiskProfile>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [RiskProfile],
    }).compileComponents();

    fixture = TestBed.createComponent(RiskProfile);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
