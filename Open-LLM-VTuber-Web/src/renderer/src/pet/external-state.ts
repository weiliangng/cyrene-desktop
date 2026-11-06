// Application-owned activity and expression arbitration, independent of the model.
export interface ExternalTask {
  task_id: string; label?: string; progress?: number;
  status: string; expires_at: number;
}
export class ExternalState {
  tasks = new Map<string, ExternalTask>();
  expression: { name: string; expires_at: number } | null = null;
  reaction: { name: string; expires_at: number } | null = null;
  awakeUntil = 0; // Application notification/reaction hold; expressions cannot extend it.

  setExpression(name: string, duration: number, now: number) {
    if (name === 'sleep') throw new Error('Sleep is controlled by the application');
    this.expression = { name, expires_at: now + duration };
  }

  task(task: ExternalTask, now = Date.now(), restoring = false) {
    const previous = this.tasks.get(task.task_id);
    if (!restoring && task.task_id.startsWith('openclaw:') && previous && previous.status !== 'running' && task.status === 'running') return;
    this.tasks.set(task.task_id, task);
    if (!restoring && task.status === 'running' && previous?.status !== 'running') {
      this.expression = null;
      this.reaction = null;
    }
    if (!restoring && previous?.status === 'running' && task.status !== 'running') {
      this.expression = null;
      if (!this.running(now).length) this.finish(task.status, now);
    }
    if (this.tasks.size > 100) {
      const old = [...this.tasks].find(([, value]) => value.status !== 'running');
      if (old) this.tasks.delete(old[0]);
    }
  }

  finish(status: string, now: number) {
    this.expression = null;
    this.reaction = { name: status === 'failed' ? 'hurt' : status === 'completed' ? 'happy' : 'neutral', expires_at: now + 3000 };
    this.awakeUntil = Math.max(this.awakeUntil, now + 3000);
  }

  running(now: number) {
    return [...this.tasks.values()].filter((task) => task.status === 'running' && task.expires_at * 1000 > now);
  }

  tick(now: number) {
    for (const task of this.tasks.values()) {
      if (task.status === 'running' && task.expires_at * 1000 <= now) {
        task.status = 'expired';
        this.expression = null;
      }
    }
    if (this.expression && this.expression.expires_at <= now) this.expression = null;
    if (this.reaction && this.reaction.expires_at <= now) this.reaction = null;
    return this.running(now).length > 0 || this.awakeUntil > now;
  }

  resolveExpression(sleeping: boolean, now: number) {
    this.tick(now);
    if (sleeping) return 'sleep';
    if (!this.running(now).length && this.reaction) return this.reaction.name;
    return this.expression?.name || 'neutral';
  }

  reset() { this.tasks.clear(); this.expression = null; this.reaction = null; this.awakeUntil = 0; }
}
