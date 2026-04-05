import { ComponentFixture, TestBed } from '@angular/core/testing';

import { RiskProfiles } from './risk-profiles';

describe('RiskProfiles', () => {
  let component: RiskProfiles;
  let fixture: ComponentFixture<RiskProfiles>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [RiskProfiles],
    }).compileComponents();

    fixture = TestBed.createComponent(RiskProfiles);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
