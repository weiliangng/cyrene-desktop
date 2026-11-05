// Time-limited external state: independent of React and of the LLM provider.
export interface ExternalTask {
  task_id: string; label?: string; progress?: number;
  status: string; expires_at: number;
}
export class ExternalState {
  tasks = new Map<string, ExternalTask>();
  expression: { name: string; expires_at: number } | null = null;
  awakeUntil = 0;

  setExpression(name: string, duration: number, now: number) {
    this.expression = { name, expires_at: now + duration };
    this.awakeUntil = Math.max(this.awakeUntil, now + duration);
  }

  task(task: ExternalTask) {
    this.tasks.set(task.task_id, task);
    if (this.tasks.size > 100) {
      const old = [...this.tasks].find(([, value]) => value.status !== 'running');
      if (old) this.tasks.delete(old[0]);
    }
  }

  running(now: number) {
    return [...this.tasks.values()].filter((task) => task.status === 'running' && task.expires_at * 1000 > now);
  }

  tick(now: number) {
    if (this.expression && this.expression.expires_at <= now) this.expression = null;
    return this.running(now).length > 0 || this.awakeUntil > now;
  }

  reset() { this.tasks.clear(); this.expression = null; this.awakeUntil = 0; }
}
