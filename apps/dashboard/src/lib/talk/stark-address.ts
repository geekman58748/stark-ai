export class StarkAddress {
  static apply(text: string): string {
    return /\bstark\b/i.test(text) ? text : `Stark, ${text}`;
  }
}
