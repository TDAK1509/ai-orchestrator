let audioContext: AudioContext | null = null

export function playPing(): void {
  try {
    emitPingTone()
  } catch {
    // allow-comment: a browser blocking audio before any user interaction is expected, not a bug to surface
  }
}

function emitPingTone(): void {
  audioContext ??= new AudioContext()
  const oscillator = audioContext.createOscillator()
  const gain = audioContext.createGain()
  oscillator.frequency.value = 880
  gain.gain.setValueAtTime(0.15, audioContext.currentTime)
  gain.gain.exponentialRampToValueAtTime(0.001, audioContext.currentTime + 0.2)
  oscillator.connect(gain).connect(audioContext.destination)
  oscillator.start()
  oscillator.stop(audioContext.currentTime + 0.2)
}
