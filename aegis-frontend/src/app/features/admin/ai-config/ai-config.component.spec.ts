import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AiConfigComponent } from './ai-config.component';

describe('AiConfigComponent', () => {
  let component: AiConfigComponent;
  let fixture: ComponentFixture<AiConfigComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AiConfigComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(AiConfigComponent);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
