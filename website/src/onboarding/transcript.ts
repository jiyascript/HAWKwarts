export const TRANSCRIPT_ACCEPT =
  ".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
export const TRANSCRIPT_MAX_BYTES = 10 * 1024 * 1024

const SUPPORTED_TYPES = ["application/pdf", "image/png", "image/jpeg"]
const SUPPORTED_EXTENSION = /\.(pdf|png|jpe?g)$/i
// Keeps the progress state readable even when a small file is read instantly.
const MIN_FEEDBACK_MS = 650

export class UploadCancelled extends Error {
  constructor() {
    super("Upload cancelled")
  }
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function validateTranscriptFile(file: File): string | null {
  if (
    !SUPPORTED_TYPES.includes(file.type) &&
    !SUPPORTED_EXTENSION.test(file.name)
  ) {
    return "That file type isn’t supported. Please choose a PDF, PNG, or JPG."
  }
  if (file.size === 0) return "That file is empty. Please choose another one."
  if (file.size > TRANSCRIPT_MAX_BYTES) {
    return `That file is ${formatBytes(file.size)}. Please choose one under 10 MB.`
  }
  return null
}

function hasSupportedSignature(bytes: Uint8Array): boolean {
  const isPdf =
    bytes[0] === 0x25 &&
    bytes[1] === 0x50 &&
    bytes[2] === 0x44 &&
    bytes[3] === 0x46
  const isPng =
    bytes[0] === 0x89 &&
    bytes[1] === 0x50 &&
    bytes[2] === 0x4e &&
    bytes[3] === 0x47
  const isJpeg = bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff
  return isPdf || isPng || isJpeg
}

export interface TranscriptUpload {
  promise: Promise<void>
  cancel: () => void
}

/**
 * No transcript service is connected yet, so "uploading" reads the file into
 * memory for this visit and verifies it is a real PDF or image. Nothing is sent
 * to a server, and the contents are not analyzed.
 */
export function uploadTranscript(
  file: File,
  onProgress: (fraction: number) => void,
): TranscriptUpload {
  const reader = new FileReader()
  const startedAt = performance.now()
  let cancelled = false

  const read = new Promise<void>((resolve, reject) => {
    reader.onprogress = (event) => {
      if (event.lengthComputable)
        onProgress(Math.min(0.95, event.loaded / event.total))
    }
    reader.onerror = () =>
      reject(
        new Error(
          "We couldn’t read that file. Please try again or choose another one.",
        ),
      )
    reader.onabort = () => reject(new UploadCancelled())
    reader.onload = () => {
      const header = new Uint8Array(
        reader.result as ArrayBuffer,
        0,
        Math.min(8, file.size),
      )
      if (hasSupportedSignature(header)) resolve()
      else
        reject(
          new Error(
            "That file doesn’t look like a valid PDF or image. Please choose another one.",
          ),
        )
    }
    reader.readAsArrayBuffer(file)
  })

  const promise = read.then(async () => {
    const remaining = MIN_FEEDBACK_MS - (performance.now() - startedAt)
    if (remaining > 0) await new Promise((r) => setTimeout(r, remaining))
    if (cancelled) throw new UploadCancelled()
    onProgress(1)
  })

  return {
    promise,
    cancel: () => {
      cancelled = true
      if (reader.readyState === FileReader.LOADING) reader.abort()
    },
  }
}
