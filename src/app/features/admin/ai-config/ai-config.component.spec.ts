import { ComponentFixture, TestBed } from '@angular/core/testing';

import { AiConfig } from './ai-config';

describe('AiConfig', () => {
  let component: AiConfig;
  let fixture: ComponentFixture<AiConfig>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AiConfig],
    }).compileComponents();

    fixture = TestBed.createComponent(AiConfig);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
