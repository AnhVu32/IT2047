'use client'

import { useState } from 'react'
import Image from 'next/image'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { getPropertyImageSrc, PROPERTY_IMAGE_FALLBACK } from '@/lib/property-images'

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

  return (
    <div className="space-y-4">
      {/* Main Image */}
      <div className="relative w-full aspect-video bg-muted rounded-lg overflow-hidden group">
        <Image
          src={imageList[mainImageIndex]}
          alt={title}
          fill
          className="object-cover"
          priority
          onError={(e) => {
            const img = e.target as HTMLImageElement
            img.src = PROPERTY_IMAGE_FALLBACK
          }}
        />

        {/* Navigation Arrows */}
        {imageList.length > 1 && (
          <>
            <Button
              variant="ghost"
              size="icon"
              className="absolute left-2 top-1/2 -translate-y-1/2 bg-black/40 hover:bg-black/60 text-white opacity-0 group-hover:opacity-100 transition-opacity"
              onClick={goToPrevious}
            >
              <ChevronLeft className="h-6 w-6" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="absolute right-2 top-1/2 -translate-y-1/2 bg-black/40 hover:bg-black/60 text-white opacity-0 group-hover:opacity-100 transition-opacity"
              onClick={goToNext}
            >
              <ChevronRight className="h-6 w-6" />
            </Button>
          </>
        )}

        {/* Image Counter */}
        <div className="absolute bottom-3 right-3 bg-black/60 text-white text-xs px-2 py-1 rounded">
          {mainImageIndex + 1} / {imageList.length}
        </div>
      </div>

      {/* Thumbnail Grid */}
      {imageList.length > 1 && (
        <div className="grid grid-cols-6 gap-2">
          {imageList.slice(0, 6).map((img, index) => (
            <button
              key={index}
              onClick={() => setMainImageIndex(index)}
              className={`relative aspect-square rounded-lg overflow-hidden border-2 transition-all ${
                mainImageIndex === index ? 'border-[#E03C31]' : 'border-border hover:border-muted-foreground'
              }`}
            >
              <Image
                src={img}
                alt={`Thumbnail ${index + 1}`}
                fill
                className="object-cover"
                onError={(e) => {
                  const img = e.target as HTMLImageElement
                  img.src = PROPERTY_IMAGE_FALLBACK
                }}
              />
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
