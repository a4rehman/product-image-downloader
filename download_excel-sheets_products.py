import os
import re
import sys
import time
import hashlib
from pathlib import Path
from urllib.parse import urlparse, unquote

import pandas as pd
import requests


# ============================================================
# CONFIGURATION
# ============================================================

# CSV file name
CSV_FILE = "excel_products_published_import.csv"

# Main output folder
OUTPUT_DIR = "SAWERA_DOWNLOADED"

# Request settings
TIMEOUT = 30
RETRIES = 3

# Image extensions we support
VALID_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".bmp",
    ".heic",
    ".heif",
}


# ============================================================
# HELPERS
# ============================================================

def clean_filename(text, max_length=100):
    """
    Make a safe Windows folder/file name.
    """

    if pd.isna(text) or text is None:
        return "UNKNOWN"

    text = str(text).strip()

    # Replace invalid Windows filename characters
    text = re.sub(r'[<>:"/\\|?*]', "_", text)

    # Remove control characters
    text = re.sub(r"[\x00-\x1f]", "", text)

    # Replace multiple spaces
    text = re.sub(r"\s+", " ", text)

    # Remove trailing dots/spaces
    text = text.rstrip(". ")

    if not text:
        text = "UNKNOWN"

    return text[:max_length]


def clean_value(value, default="Not specified"):
    """
    Convert empty/NaN values into readable text.
    """

    if pd.isna(value):
        return default

    value = str(value).strip()

    if not value or value.lower() in {
        "nan",
        "none",
        "null",
        "nat",
    }:
        return default

    return value


def get_image_extension(url, content_type=None):
    """
    Determine image extension from URL/content type.
    """

    try:
        path = urlparse(url).path
        ext = Path(unquote(path)).suffix.lower()

        if ext in VALID_EXTENSIONS:
            return ext

    except Exception:
        pass

    # Try Content-Type
    if content_type:
        content_type = content_type.lower()

        mapping = {
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "image/gif": ".gif",
            "image/bmp": ".bmp",
            "image/heic": ".heic",
            "image/heif": ".heif",
        }

        for mime, extension in mapping.items():
            if mime in content_type:
                return extension

    return ".jpg"


def split_image_urls(value):
    """
    Your CSV stores multiple image URLs separated by |.
    """

    if pd.isna(value):
        return []

    value = str(value).strip()

    if not value:
        return []

    urls = []

    for url in value.split("|"):
        url = url.strip()

        if url and url.startswith(("http://", "https://")):
            urls.append(url)

    return urls


def safe_folder_name(sku, name):
    """
    Create folder name:

    SKU_PRODUCT_NAME
    """

    sku = clean_filename(sku)
    name = clean_filename(name)

    return f"{sku}_{name}"


def calculate_url_hash(url):
    """
    Create unique hash for duplicate detection.
    """

    return hashlib.md5(url.encode("utf-8")).hexdigest()


# ============================================================
# DOWNLOAD IMAGE
# ============================================================

def download_image(url, output_path):
    """
    Download one image with retry support.
    """

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        ),
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }

    for attempt in range(1, RETRIES + 1):

        try:

            response = requests.get(
                url,
                headers=headers,
                timeout=TIMEOUT,
                stream=True,
            )

            response.raise_for_status()

            extension = get_image_extension(
                url,
                response.headers.get("Content-Type"),
            )

            final_path = output_path.with_suffix(extension)

            with open(final_path, "wb") as file:

                for chunk in response.iter_content(chunk_size=1024 * 64):

                    if chunk:
                        file.write(chunk)

            return True, final_path

        except Exception as error:

            if attempt < RETRIES:
                time.sleep(2)

            else:
                return False, str(error)

    return False, "Unknown error"


# ============================================================
# CREATE PRODUCT INFO
# ============================================================

def create_product_info(row, folder, downloaded_images, failed_images):

    product_name = clean_value(row.get("name"))
    description = clean_value(row.get("description"))
    price = clean_value(row.get("price"))
    compare_price = clean_value(row.get("compare at price"))
    category = clean_value(row.get("category"))
    brand = clean_value(row.get("brand"))
    sku = clean_value(row.get("sku"))
    stock = clean_value(row.get("stock"))
    sizes = clean_value(row.get("sizes"))
    colors = clean_value(row.get("colors"))
    fabric = clean_value(row.get("fabric"))
    tags = clean_value(row.get("tags"))

    lines = []

    lines.append("=" * 60)
    lines.append("SAWERA COLLECTION - PRODUCT INFORMATION")
    lines.append("=" * 60)
    lines.append("")

    lines.append(f"Product Name:")
    lines.append(product_name)
    lines.append("")

    lines.append(f"SKU:")
    lines.append(sku)
    lines.append("")

    lines.append(f"Brand:")
    lines.append(brand)
    lines.append("")

    lines.append(f"Category:")
    lines.append(category)
    lines.append("")

    lines.append(f"Price:")
    lines.append(price)
    lines.append("")

    lines.append(f"Compare At Price:")
    lines.append(compare_price)
    lines.append("")

    lines.append(f"Stock:")
    lines.append(stock)
    lines.append("")

    lines.append(f"Sizes:")
    lines.append(sizes)
    lines.append("")

    lines.append(f"Colors:")
    lines.append(colors)
    lines.append("")

    lines.append(f"Fabric:")
    lines.append(fabric)
    lines.append("")

    lines.append(f"Tags:")
    lines.append(tags)
    lines.append("")

    lines.append("-" * 60)
    lines.append("DESCRIPTION")
    lines.append("-" * 60)
    lines.append("")

    lines.append(description)
    lines.append("")

    lines.append("-" * 60)
    lines.append("DOWNLOADED IMAGES")
    lines.append("-" * 60)
    lines.append("")

    if downloaded_images:

        for image in downloaded_images:
            lines.append(image.name)

    else:
        lines.append("No images downloaded.")

    if failed_images:

        lines.append("")
        lines.append("-" * 60)
        lines.append("FAILED IMAGE DOWNLOADS")
        lines.append("-" * 60)
        lines.append("")

        for failed_url, error in failed_images:

            lines.append(f"URL: {failed_url}")
            lines.append(f"ERROR: {error}")
            lines.append("")

    info_file = folder / "product_info.txt"

    with open(
        info_file,
        "w",
        encoding="utf-8",
    ) as file:

        file.write("\n".join(lines))

    return info_file


# ============================================================
# MAIN PROCESS
# ============================================================

def main():

    print()
    print("=" * 70)
    print("        SAWERA COLLECTION IMAGE DOWNLOADER")
    print("=" * 70)
    print()

    # Support custom CSV passed via argument or discover existing CSV
    csv_path = Path(CSV_FILE)
    if len(sys.argv) > 1 and Path(sys.argv[1]).is_file():
        csv_path = Path(sys.argv[1])
    elif not csv_path.exists():
        alternates = [
            Path("excel_products_published_import.csv"),
            Path("sawera_products_published_import(3).csv"),
            Path("sawera_products_published_import.csv"),
        ]
        for alt in alternates:
            if alt.exists():
                csv_path = alt
                break
        else:
            all_csvs = list(Path(".").glob("*.csv"))
            if all_csvs:
                csv_path = all_csvs[0]

    if not csv_path.exists():

        print(f"ERROR: CSV file not found:")
        print(csv_path.resolve())
        print()

        input("Press Enter to exit...")
        sys.exit(1)

    # --------------------------------------------------------
    # Read CSV
    # --------------------------------------------------------

    print("Reading CSV...")

    try:

        df = pd.read_csv(
            csv_path,
            keep_default_na=False,
        )

    except Exception as error:

        print("ERROR reading CSV:")
        print(error)

        input("Press Enter to exit...")
        sys.exit(1)

    print(f"Products found: {len(df)}")
    print()

    # --------------------------------------------------------
    # Check required columns
    # --------------------------------------------------------

    required_columns = [
        "name",
        "sku",
        "images",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:

        print("ERROR: Missing required columns:")

        for column in missing_columns:
            print(f"  - {column}")

        input("Press Enter to exit...")
        sys.exit(1)

    # --------------------------------------------------------
    # Create output folder
    # --------------------------------------------------------

    output_path = Path(OUTPUT_DIR)

    output_path.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # Tracking
    # --------------------------------------------------------

    total_products = len(df)

    total_images = 0
    successful_images = 0
    failed_images_count = 0

    failed_products = []

    global_downloaded_urls = set()

    # --------------------------------------------------------
    # Process products
    # --------------------------------------------------------

    for index, row in df.iterrows():

        product_number = index + 1

        product_name = clean_value(
            row.get("name"),
            "UNKNOWN PRODUCT",
        )

        sku = clean_value(
            row.get("sku"),
            f"PRODUCT-{product_number}",
        )

        print()
        print("-" * 70)
        print(
            f"[{product_number}/{total_products}] "
            f"{product_name}"
        )
        print(f"SKU: {sku}")

        # ----------------------------------------------------
        # Folder
        # ----------------------------------------------------

        folder_name = safe_folder_name(
            sku,
            product_name,
        )

        product_folder = output_path / folder_name

        product_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        # ----------------------------------------------------
        # Image URLs
        # ----------------------------------------------------

        image_urls = split_image_urls(
            row.get("images")
        )

        print(
            f"Images found: {len(image_urls)}"
        )

        total_images += len(image_urls)

        downloaded_images = []
        failed_images = []

        local_url_hashes = set()

        # ----------------------------------------------------
        # Download images
        # ----------------------------------------------------

        image_number = 1

        for url in image_urls:

            url_hash = calculate_url_hash(url)

            # Duplicate inside same product
            if url_hash in local_url_hashes:

                print(
                    f"  SKIP duplicate: "
                    f"{image_number}"
                )

                continue

            local_url_hashes.add(url_hash)

            # Duplicate globally
            if url in global_downloaded_urls:

                print(
                    f"  SKIP already downloaded URL: "
                    f"{image_number}"
                )

                continue

            global_downloaded_urls.add(url)

            base_filename = (
                product_folder
                / f"{image_number:02d}"
            )

            print(
                f"  Downloading image "
                f"{image_number}..."
            )

            success, result = download_image(
                url,
                base_filename,
            )

            if success:

                print(
                    f"    OK -> {result.name}"
                )

                downloaded_images.append(result)

                successful_images += 1

            else:

                print(
                    f"    FAILED -> {result}"
                )

                failed_images.append(
                    (url, result)
                )

                failed_images_count += 1

            image_number += 1

        # ----------------------------------------------------
        # Product info TXT
        # ----------------------------------------------------

        info_file = create_product_info(
            row,
            product_folder,
            downloaded_images,
            failed_images,
        )

        print(
            f"  Product info -> "
            f"{info_file.name}"
        )

        # ----------------------------------------------------
        # Failed product tracking
        # ----------------------------------------------------

        if failed_images:

            failed_products.append({
                "product": product_name,
                "sku": sku,
                "failed_images": len(failed_images),
            })

    # ========================================================
    # CREATE SUMMARY REPORT
    # ========================================================

    summary_file = output_path / "DOWNLOAD_SUMMARY.txt"

    summary = []

    summary.append("=" * 70)
    summary.append("SAWERA COLLECTION DOWNLOAD SUMMARY")
    summary.append("=" * 70)
    summary.append("")

    summary.append(
        f"Total Products: {total_products}"
    )

    summary.append(
        f"Total Image URLs: {total_images}"
    )

    summary.append(
        f"Successfully Downloaded: {successful_images}"
    )

    summary.append(
        f"Failed Downloads: {failed_images_count}"
    )

    summary.append("")

    summary.append("-" * 70)
    summary.append("FAILED PRODUCTS")
    summary.append("-" * 70)
    summary.append("")

    if failed_products:

        for item in failed_products:

            summary.append(
                f"Product: {item['product']}"
            )

            summary.append(
                f"SKU: {item['sku']}"
            )

            summary.append(
                f"Failed Images: "
                f"{item['failed_images']}"
            )

            summary.append("")

    else:

        summary.append(
            "No failed product downloads."
        )

    with open(
        summary_file,
        "w",
        encoding="utf-8",
    ) as file:

        file.write("\n".join(summary))

    # ========================================================
    # FINISHED
    # ========================================================

    print()
    print("=" * 70)
    print("DOWNLOAD COMPLETED")
    print("=" * 70)
    print()

    print(
        f"Products:             {total_products}"
    )

    print(
        f"Image URLs:           {total_images}"
    )

    print(
        f"Downloaded:           {successful_images}"
    )

    print(
        f"Failed:               {failed_images_count}"
    )

    print()
    print(
        f"Output folder:"
    )

    print(
        output_path.resolve()
    )

    print()
    print(
        "A product_info.txt file was created "
        "inside every product folder."
    )

    print()

    input("Press Enter to exit...")


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()