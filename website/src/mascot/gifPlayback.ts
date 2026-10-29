export function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms))
}

export function afterNextPaint(): Promise<void> {
  return new Promise((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve()))
  })
}

// A non-looping GIF that has already played stays on its last frame wherever
// that URL is reused, so each playback gets a fresh object URL. The bytes are
// fetched once and shared.
const gifBlobs = new Map<string, Promise<Blob>>()
let gifPlayCount = 0

export function loadGifBlob(src: string): Promise<Blob> {
  let blob = gifBlobs.get(src)
  if (!blob) {
    blob = fetch(src).then((response) => {
      if (!response.ok) throw new Error(`Could not load ${src}`)
      return response.blob()
    })
    blob.catch(() => gifBlobs.delete(src))
    gifBlobs.set(src, blob)
  }
  return blob
}

export interface FreshGif {
  url: string
  release: () => void
}

export async function freshGif(src: string): Promise<FreshGif> {
  let url: string
  let release = () => {}
  try {
    const blob = await Promise.race([
      loadGifBlob(src),
      sleep(1500).then(() => {
        throw new Error("GIF fetch timed out")
      }),
    ])
    const objectUrl = URL.createObjectURL(blob)
    url = objectUrl
    release = () => URL.revokeObjectURL(objectUrl)
  } catch {
    // A unique query string still yields a fresh, restartable image.
    url = `${src}?play=${++gifPlayCount}`
  }
  // Decode ahead (off-screen, so the animation clock hasn't started) to avoid a blank swap.
  const probe = new Image()
  probe.src = url
  await probe.decode().catch(() => undefined)
  return { url, release }
}
