export class AudioRecording {
  static supported(): boolean {
    return (
      typeof MediaRecorder !== "undefined" &&
      typeof navigator !== "undefined" &&
      Boolean(navigator.mediaDevices?.getUserMedia)
    );
  }
}
