// Small state machine shared by the UI and deterministic idle-behaviour tests.
export const SLEEP_DELAY_MS = 5000;
export type ActivitySource = 'model' | 'panel' | 'focus' | 'draft' | 'conversation' | 'external' | 'speech';

export class PetActivity {
  sleeping = true;
  private active = new Set<ActivitySource>();
  private lastActivity = -Infinity;

  constructor(readonly delay = SLEEP_DELAY_MS) {}

  set(source: ActivitySource, active: boolean, now: number): void {
    if (active) {
      this.active.add(source);
      this.sleeping = false;
      this.lastActivity = now;
    } else if (this.active.delete(source)) {
      this.lastActivity = now;
    }
  }

  sleep(): void { this.active.clear(); this.lastActivity = -Infinity; this.sleeping = true; }

  tick(now: number): boolean {
    this.sleeping = this.active.size === 0 && now - this.lastActivity >= this.delay;
    return this.sleeping;
  }
}
