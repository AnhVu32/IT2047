'use client'

import { useState } from 'react'
import Image from 'next/image'
import { ChevronLeft, ChevronRight, Images } from 'lucide-react'
import { getPropertyImageSrc, PROPERTY_IMAGE_FALLBACK } from '@/lib/property-images'
import { cn } from '@/lib/utils'

interface ImageGalleryProps {
  images: string[]
  title: string
}

export function ImageGallery({ images, title }: ImageGalleryProps) {
  const propertyImages = (images || [])
    .filter((image) => Boolean(image?.trim()))
    .map(getPropertyImageSrc)
  const imageList = propertyImages.length > 0 ? propertyImages : [PROPERTY_IMAGE_FALLBACK]
  const [mainImageIndex, setMainImageIndex] = useState(0)

  const goToPrevious = () => {
    setMainImageIndex((prev) => (prev === 0 ? imageList.length - 1 : prev - 1))
  }

  const goToNext = () => {
    setMainImageIndex((prev) => (prev === imageList.length - 1 ? 0 : prev + 1))
  }

  const handleImageError = (e: React.SyntheticEvent<HTMLImageElement>) => {
    e.currentTarget.src = PROPERTY_IMAGE_FALLBACK
  }

  return (
    <div className="space-y-2">
      <div
        className="group relative aspect-[16/10] w-full overflow-hidden rounded-xl bg-muted"
        onKeyDown={(e) => {
          if (e.key === 'ArrowLeft') goToPrevious()
          if (e.key === 'ArrowRight') goToNext()
        }}
        tabIndex={imageList.length > 1 ? 0 : undefined}
        aria-label="Thư viện ảnh, dùng phím mũi tên để chuyển ảnh"
      >
        <Image
          src={imageList[mainImageIndex]}
          alt={title}
          fill
          className="object-cover"
          priority
          onError={handleImageError}
        />

        {imageList.length > 1 && (
          <>
            <button
              type="button"
              aria-label="Ảnh trước"
              className="absolute left-3 top-1/2 -translate-y-1/2 rounded-full bg-white/90 p-2 text-slate-800 shadow-md transition-opacity hover:bg-white md:opacity-0 md:group-hover:opacity-100"
              onClick={goToPrevious}
            >
              <ChevronLeft className="h-5 w-5" />
            </button>
            <button
              type="button"
              aria-label="Ảnh sau"
              className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full bg-white/90 p-2 text-slate-800 shadow-md transition-opacity hover:bg-white md:opacity-0 md:group-hover:opacity-100"
              onClick={goToNext}
            >
              <ChevronRight className="h-5 w-5" />
            </button>
          </>
        )}

        <span className="absolute bottom-3 right-3 flex items-center gap-1.5 rounded-full bg-black/60 px-3 py-1 text-xs font-medium text-white">
          <Images className="h-3.5 w-3.5" />
          {mainImageIndex + 1} / {imageList.length}
        </span>
      </div>

      {imageList.length > 1 && (
        <div className="flex gap-2 overflow-x-auto pb-1 [scrollbar-width:thin]">
          {imageList.map((img, index) => (
            <button
              key={index}
              type="button"
              onClick={() => setMainImageIndex(index)}
              aria-label={`Xem ảnh ${index + 1}`}
              aria-current={mainImageIndex === index}
              className={cn(
                'relative h-16 w-24 flex-shrink-0 overflow-hidden rounded-lg transition-all md:h-20 md:w-28',
                mainImageIndex === index ? 'ring-2 ring-primary ring-offset-2 ring-offset-background' : 'opacity-70 hover:opacity-100',
              )}
            >
              <Image src={img} alt="" fill className="object-cover" onError={handleImageError} />
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
