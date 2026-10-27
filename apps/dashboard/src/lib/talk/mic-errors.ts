export class MicErrors {
  static copy(error?: string): string {
    if (error === "not-allowed" || error === "service-not-allowed") {
      return "Microphone blocked — allow mic access for this page, or type below.";
    }
    if (error === "no-speech") {
      return "I didn't hear anything. Tap and try again.";
    }
    return "I didn't catch that — tap to try again, or type below.";
  }
}
