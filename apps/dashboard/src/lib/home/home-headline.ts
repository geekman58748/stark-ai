export class HomeHeadline {
  static text(needing: number): string {
    switch (needing) {
      case 0:
        return "Everything’s covered";
      case 1:
        return "One thing needs you";
      case 2:
        return "Two things need you";
      default:
        return `${needing} things need you`;
    }
  }
}
