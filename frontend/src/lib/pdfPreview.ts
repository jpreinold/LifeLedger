interface PdfViewport {
  width: number
  height: number
}

interface PdfPage {
  getViewport: (options: { scale: number }) => PdfViewport
  render: (options: { canvasContext: CanvasRenderingContext2D; viewport: PdfViewport }) => PdfRenderTask
}

export interface PdfDocument {
  numPages: number
  getPage: (pageNumber: number) => Promise<PdfPage>
  destroy: () => Promise<void>
}

export interface PdfRenderTask {
  promise: Promise<void>
  cancel: () => void
}

let pdfjsPromise: Promise<typeof import('pdfjs-dist')> | null = null

async function loadPdfjs() {
  if (!pdfjsPromise) {
    pdfjsPromise = import('pdfjs-dist').then((pdfjs) => {
      pdfjs.GlobalWorkerOptions.workerSrc = new URL('pdfjs-dist/build/pdf.worker.mjs', import.meta.url).toString()
      return pdfjs
    })
  }

  return pdfjsPromise
}

export async function loadPdfDocument(url: string): Promise<PdfDocument> {
  const pdfjs = await loadPdfjs()
  const loadingTask = pdfjs.getDocument({
    disableAutoFetch: true,
    url,
    withCredentials: false,
  })

  return loadingTask.promise as unknown as Promise<PdfDocument>
}

export async function createPdfPageRenderTask({
  canvas,
  document,
  pageNumber,
  targetWidth,
  zoom = 1,
}: {
  canvas: HTMLCanvasElement
  document: PdfDocument
  pageNumber: number
  targetWidth: number
  zoom?: number
}): Promise<PdfRenderTask> {
  const page = await document.getPage(pageNumber)
  const baseViewport = page.getViewport({ scale: 1 })
  const deviceScale = Math.max(window.devicePixelRatio || 1, 1)
  const fitScale = targetWidth > 0 ? targetWidth / baseViewport.width : 1
  const viewport = page.getViewport({ scale: fitScale * zoom * deviceScale })
  const context = canvas.getContext('2d')

  if (!context) {
    throw new Error('Unable to prepare the PDF canvas.')
  }

  const displayWidth = Math.max(1, Math.floor(viewport.width / deviceScale))
  const displayHeight = Math.max(1, Math.floor(viewport.height / deviceScale))
  canvas.width = Math.max(1, Math.floor(viewport.width))
  canvas.height = Math.max(1, Math.floor(viewport.height))
  canvas.style.width = `${displayWidth}px`
  canvas.style.height = `${displayHeight}px`
  context.clearRect(0, 0, canvas.width, canvas.height)

  return page.render({ canvasContext: context, viewport })
}

