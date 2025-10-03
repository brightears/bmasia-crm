#!/usr/bin/env python3
"""
Script to crop whitespace from BMAsia logo.
This removes excess white space around the logo to make it appear larger in PDFs.
"""

from PIL import Image
import os

def crop_logo(input_path, output_path=None, padding=20):
    """
    Crop white space from logo image.

    Args:
        input_path: Path to the input logo image
        output_path: Path to save cropped logo (defaults to overwriting input)
        padding: Pixels of padding to add around the cropped logo
    """
    # Load the image
    img = Image.open(input_path)

    # Convert to RGBA if not already (to handle transparency)
    if img.mode != 'RGBA':
        img = img.convert('RGBA')

    # Get the bounding box of non-white/non-transparent content
    # Create a background layer
    bg = Image.new('RGBA', img.size, (255, 255, 255, 255))

    # Composite the image over white background
    composite = Image.alpha_composite(bg, img)

    # Convert to RGB for bbox calculation
    rgb = composite.convert('RGB')

    # Get bounding box by finding non-white pixels
    # We'll check each pixel and find the bounds
    pixels = rgb.load()
    width, height = rgb.size

    # Find bounds
    min_x, min_y = width, height
    max_x, max_y = 0, 0

    # Define what we consider "white" (with some tolerance for anti-aliasing)
    WHITE_THRESHOLD = 250

    for y in range(height):
        for x in range(width):
            r, g, b = pixels[x, y]
            # If pixel is not white
            if r < WHITE_THRESHOLD or g < WHITE_THRESHOLD or b < WHITE_THRESHOLD:
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)

    # Add padding
    min_x = max(0, min_x - padding)
    min_y = max(0, min_y - padding)
    max_x = min(width, max_x + padding)
    max_y = min(height, max_y + padding)

    # Crop the original image (with transparency preserved)
    cropped = img.crop((min_x, min_y, max_x, max_y))

    # Print info
    print(f"Original size: {img.size}")
    print(f"Cropped size: {cropped.size}")
    print(f"Reduction: {(1 - (cropped.size[0] * cropped.size[1]) / (img.size[0] * img.size[1])) * 100:.1f}%")

    # Save the cropped image
    if output_path is None:
        output_path = input_path

    cropped.save(output_path, 'PNG', optimize=True)
    print(f"Saved cropped logo to: {output_path}")

    return output_path

if __name__ == '__main__':
    # Path to the logo
    logo_path = os.path.join(
        os.path.dirname(__file__),
        'crm_app', 'static', 'crm_app', 'images', 'bmasia_logo.png'
    )

    if not os.path.exists(logo_path):
        print(f"Error: Logo file not found at {logo_path}")
        exit(1)

    # Create a backup first
    backup_path = logo_path.replace('.png', '_original.png')
    if not os.path.exists(backup_path):
        print(f"Creating backup at: {backup_path}")
        img = Image.open(logo_path)
        img.save(backup_path)

    # Crop the logo
    print("Cropping logo...")
    crop_logo(logo_path, padding=20)
    print("Done!")
