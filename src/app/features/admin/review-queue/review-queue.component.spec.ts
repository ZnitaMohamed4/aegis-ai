import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ReviewQueue } from './review-queue';

describe('ReviewQueue', () => {
  let component: ReviewQueue;
  let fixture: ComponentFixture<ReviewQueue>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ReviewQueue],
    }).compileComponents();

    fixture = TestBed.createComponent(ReviewQueue);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
