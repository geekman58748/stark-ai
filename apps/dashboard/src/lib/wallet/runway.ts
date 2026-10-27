export class Runway {
  static note(balance: number, spentThisMonth: number): string {
    if (spentThisMonth <= 0) return "ready for your bills";
    const months = Math.floor(balance / spentThisMonth);
    if (months < 1) return "less than a month of bills";
    return `enough for about ${months} month${months === 1 ? "" : "s"} of bills`;
  }
}
